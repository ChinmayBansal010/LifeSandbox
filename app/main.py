import asyncio
import importlib.util
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from functools import lru_cache

import sentry_sdk
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import router as auth_router
from app.api.life import router as life_router
from app.api.memory import router as memory_router
from app.api.workflow import router as workflow_router
from app.core.config import get_settings
from app.core.rate_limit import SlidingWindowRateLimiter
from app.core.security import Principal, current_principal
from app.domain.simulation import SimulationRequest, simulate
from app.integrations.google import router as integrations_router
from app.integrations.telegram import (
    router as telegram_router,
)
from app.integrations.telegram import (
    run_telegram_polling,
    telegram_is_configured,
)
from app.persistence.models import (
    Base,
    ConversationRow,
    FeedbackRow,
    FileRow,
    IntegrationConnectionRow,
    MessageRow,
    PromptTraceRow,
)
from app.persistence.session import engine, get_session
from app.providers.browser_use import is_configured as browser_use_is_configured
from app.providers.llm import LLMError
from app.providers.mem0 import is_configured as mem0_is_configured
from app.services.chat import run_chat
from app.services.tool_tracker import clear_traces, get_stats, get_trace_by_id, get_traces
from app.tools import catalog as _tool_catalog  # noqa: F401 - registers built-in capabilities
from app.tools.registry import CapabilityStatus, registry

class _SettingsProxy:
    def __getattr__(self, name: str):
        return getattr(get_settings(), name)

    def __setattr__(self, name: str, value):
        setattr(get_settings(), name, value)


settings = _SettingsProxy()


@lru_cache(maxsize=1)
def _whisper_model():
    import importlib

    whisper_module = importlib.import_module("faster_whisper")
    return whisper_module.WhisperModel(
        settings.stt_model,
        device=settings.stt_device,
        compute_type=settings.stt_compute_type,
    )


@lru_cache(maxsize=1)
def _kokoro_pipeline():
    import importlib

    return importlib.import_module("kokoro").KPipeline(lang_code="a")


logging.basicConfig(
    level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.05, send_default_pii=False)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Dev convenience only; production schema is managed by Alembic migrations.
    if settings.app_env != "production":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    telegram_task = None
    telegram_stop = asyncio.Event()
    if (
        telegram_is_configured()
        and getattr(settings, "telegram_polling_enabled", True)
        and not os.environ.get("PYTEST_CURRENT_TEST")
    ):
        telegram_task = asyncio.create_task(run_telegram_polling(telegram_stop))

    try:
        yield
    finally:
        if telegram_task:
            telegram_stop.set()
            telegram_task.cancel()
            try:
                await asyncio.wait_for(telegram_task, timeout=5.0)
            except (TimeoutError, asyncio.CancelledError):
                pass
        await engine.dispose()


app = FastAPI(title="Life Sandbox API", version="0.1.0", lifespan=lifespan)
_rate_limiter = SlidingWindowRateLimiter(limit=settings.rate_limit_per_minute)
app.include_router(life_router)
app.include_router(auth_router)
app.include_router(memory_router)
app.include_router(workflow_router)
app.include_router(integrations_router)
app.include_router(telegram_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
)


@app.exception_handler(LLMError)
async def llm_error(_: Request, exc: LLMError):
    logging.getLogger("life_sandbox.provider").warning(
        "Model provider failure provider=%s status_code=%s",
        exc.provider,
        exc.status_code,
    )
    return JSONResponse(
        status_code=502,
        content={
            "error": {
                "code": "llm_provider_error",
                "provider": exc.provider,
                "upstream_status": exc.status_code,
                "message": str(exc),
            }
        },
    )


@app.middleware("http")
async def request_id(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = rid
    if (
        settings.app_env == "production"
        and request.url.path.startswith("/api/")
        and request.method != "OPTIONS"
    ):
        client_key = request.client.host if request.client else "unknown"
        if not _rate_limiter.allow(client_key):
            return JSONResponse(
                status_code=429,
                headers={"X-Request-ID": rid, "Retry-After": "60"},
                content={
                    "error": {
                        "code": "rate_limit_exceeded",
                        "message": "Too many requests. Wait before trying again.",
                    }
                },
            )
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response


@app.exception_handler(Exception)
async def unhandled_error(_: Request, exc: Exception):
    logging.getLogger("life_sandbox").exception("Unhandled request failure", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": {"code": "internal_error", "message": "The request could not be completed"}
        },
    )


@app.get("/health")
async def health():
    return {"status": "ok", "environment": settings.app_env}


@app.get("/ready")
async def readiness(db: AsyncSession = Depends(get_session)):
    try:
        await db.execute(select(1))
        return {"status": "ready", "database": "ok"}
    except Exception as exc:
        raise HTTPException(
            503, detail={"code": "dependency_unavailable", "message": "Database is unavailable"}
        ) from exc


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    conversation_id: str | None = None
    history: list[dict[str, str]] = Field(default_factory=list, max_length=12)
    remember: bool = False
    browse: bool = False
    attachment_ids: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message cannot be blank")
        return value


@app.get("/api/v1/capabilities")
async def capabilities():
    stt_available = (
        settings.stt_provider == "faster_whisper"
        and importlib.util.find_spec("faster_whisper") is not None
    )
    tts_available = (
        settings.tts_provider == "kokoro"
        and importlib.util.find_spec("kokoro") is not None
        and importlib.util.find_spec("numpy") is not None
        and importlib.util.find_spec("soundfile") is not None
    )
    image_available = settings.vision_enabled and settings.llm_provider in {"nebius", "openrouter"}
    return {
        "mem0_enabled": mem0_is_configured(),
        "browser_use_enabled": browser_use_is_configured(),
        "stt_enabled": stt_available,
        "tts_enabled": tts_available,
        "file_upload_enabled": True,
        "image_understanding_enabled": image_available,
    }


def _google_oauth_configured() -> bool:
    return bool(
        settings.google_oauth_client_id
        and settings.google_oauth_client_secret
        and settings.google_oauth_callback_url
        and settings.google_token_encryption_key
    )


def _telegram_configured() -> bool:
    return bool(settings.telegram_bot_token)


@app.get("/api/v1/plugins")
async def plugin_catalogue(
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    """Return registry-backed, sanitized tool metadata and owner-specific connection state."""
    rows = (
        await db.scalars(
            select(IntegrationConnectionRow).where(
                IntegrationConnectionRow.user_id == principal.user_id,
                IntegrationConnectionRow.provider == "google",
                IntegrationConnectionRow.status == "connected",
            )
        )
    ).all()
    connection_scopes = [set(json.loads(row.scopes)) for row in rows]
    google_configured = _google_oauth_configured()
    tools = []
    for definition in registry.definitions():
        status: CapabilityStatus = "available"
        setup = "Ready to use in chat."
        if definition.provider_id == "google":
            if not google_configured:
                status = "requires_setup"
                setup = "A server administrator must configure Google OAuth and token encryption."
            elif not rows:
                status = "requires_connection"
                setup = "Connect a Google account and select the permissions shown here."
            elif not any(
                set(definition.required_permissions).issubset(scopes)
                for scopes in connection_scopes
            ):
                status = "permission_required"
                setup = "Reconnect Google and grant the required permission for this operation."
            else:
                status = "connected"
                setup = "A connected Google account has the required permission."
        elif definition.provider_id == "telegram":
            if not _telegram_configured():
                status = "requires_setup"
                setup = "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env."
            else:
                status = "available"
                setup = "Ready to send notifications and messages to your Telegram."
        elif definition.provider_id == "research":
            if settings.research_provider == "disabled":
                status = "disabled"
                setup = (
                    "Set RESEARCH_PROVIDER=tavily and configure TAVILY_API_KEY "
                    "to enable live search."
                )
            else:
                status = "available"
                setup = (
                    "Live research is configured; provider health is checked when a search runs."
                )
        tools.append(definition.public_description(status, setup))
    return {"tools": tools, "refreshed_at": datetime.now(UTC)}


@app.get("/api/v1/plugins/executions")
async def plugin_executions(
    limit: int = 30,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    """Return safe tool execution summaries from this owner's persisted chat traces."""
    limit = max(1, min(limit, 100))
    rows = (
        await db.scalars(
            select(PromptTraceRow)
            .where(PromptTraceRow.user_id == principal.user_id)
            .order_by(PromptTraceRow.started_at.desc())
            .limit(limit)
        )
    ).all()
    executions = []
    for row in rows:
        try:
            events = json.loads(row.tools_accessed or "[]")
        except (TypeError, json.JSONDecodeError):
            events = []
        for event in events:
            name = event.get("tool_name")
            if not isinstance(name, str) or name in {"llm_completion", "intent_classifier"}:
                continue
            definition = registry.get(name)
            executions.append(
                {
                    "id": event.get("id"),
                    "tool_id": name,
                    "display_name": definition.display_name if definition else name,
                    "provider": definition.provider_id if definition else "unknown",
                    "status": event.get("status", "unknown"),
                    "started_at": event.get("started_at"),
                    "completed_at": event.get("completed_at"),
                    "duration_ms": event.get("duration_ms"),
                }
            )
    return {"executions": executions[:limit]}


@app.get("/api/v1/skills")
async def list_skills():
    from app.skills.registry import get_all_skills_data

    return {"skills": get_all_skills_data()}


@app.post("/api/v1/chat")
async def chat(
    payload: ChatRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    if payload.browse and not browser_use_is_configured():
        raise HTTPException(
            503,
            detail={
                "code": "browser_use_not_configured",
                "message": "Browser Use is disabled or not configured",
            },
        )
    try:
        result = await run_chat(
            db,
            principal.user_id,
            payload.message,
            payload.conversation_id,
            payload.history,
            payload.remember,
            payload.browse,
            request.is_disconnected,
            payload.attachment_ids,
        )
    except LLMError as exc:
        timeout = exc.code == "timeout"
        message = (
            "Model response timed out (OpenRouter). Mem0 save was not attempted."
            if timeout and exc.provider == "openrouter"
            else "The model provider failed. Mem0 save was not attempted."
        )
        return JSONResponse(
            status_code=504 if timeout else 502,
            content={
                "error": {
                    "code": "llm_provider_error",
                    "provider": exc.provider,
                    "upstream_status": exc.status_code,
                    "message": message,
                    "mem0_opt_in": payload.remember,
                    "mem0_search_status": "not_requested",
                    "mem0_save_status": "not_attempted" if payload.remember else "not_requested",
                    "failure_detail": {
                        "provider": exc.provider,
                        "stage": "llm_generate",
                        "code": exc.code,
                        "message": message,
                        "retriable": True,
                    },
                }
            },
        )
    except ValueError as exc:
        raise HTTPException(
            422,
            detail={"code": "invalid_attachment", "message": str(exc)},
        ) from exc
    if result is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Conversation not found"})
    return result


@app.post("/api/v1/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    if payload.browse and not browser_use_is_configured():
        raise HTTPException(
            503,
            detail={
                "code": "browser_use_not_configured",
                "message": "Browser Use is disabled or not configured",
            },
        )
    import json

    from fastapi.responses import StreamingResponse

    async def events():
        run_id = str(uuid.uuid4())
        yield f"event: run.started\ndata: {json.dumps({'run_id': run_id})}\n\n"
        try:
            result = await run_chat(
                db,
                principal.user_id,
                payload.message,
                payload.conversation_id,
                payload.history,
                payload.remember,
                payload.browse,
                request.is_disconnected,
                payload.attachment_ids,
            )
            if result is None:
                event_data = {"run_id": run_id, "code": "not_found"}
                yield f"event: run.failed\ndata: {json.dumps(event_data)}\n\n"
                return
            delta = {"run_id": run_id, "text": result["reply"]}
            yield f"event: assistant.delta\ndata: {json.dumps(delta)}\n\n"
            yield f"event: run.completed\ndata: {json.dumps({'run_id': run_id, **result})}\n\n"
        except Exception:
            event_data = {"run_id": run_id, "code": "provider_error"}
            yield f"event: run.failed\ndata: {json.dumps(event_data)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/v1/conversations", status_code=201)
async def create_conversation(
    principal: Principal = Depends(current_principal), db: AsyncSession = Depends(get_session)
):
    row = ConversationRow(user_id=principal.user_id)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {"id": row.id, "title": row.title, "created_at": row.created_at}


@app.get("/api/v1/conversations")
async def conversations(
    principal: Principal = Depends(current_principal), db: AsyncSession = Depends(get_session)
):
    rows = (
        await db.scalars(
            select(ConversationRow)
            .where(ConversationRow.user_id == principal.user_id)
            .order_by(ConversationRow.updated_at.desc())
            .limit(100)
        )
    ).all()
    return {
        "items": [
            {"id": r.id, "title": r.title, "created_at": r.created_at, "updated_at": r.updated_at}
            for r in rows
        ]
    }


@app.get("/api/v1/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    row = await db.scalar(
        select(ConversationRow).where(
            ConversationRow.id == conversation_id, ConversationRow.user_id == principal.user_id
        )
    )
    if row is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Conversation not found"})
    return {
        "id": row.id,
        "title": row.title,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


class RenameConversationPayload(BaseModel):
    title: str = Field(min_length=1, max_length=200)


@app.patch("/api/v1/conversations/{conversation_id}")
async def rename_conversation(
    conversation_id: str,
    payload: RenameConversationPayload,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    row = await db.scalar(
        select(ConversationRow).where(
            ConversationRow.id == conversation_id, ConversationRow.user_id == principal.user_id
        )
    )
    if row is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Conversation not found"})
    row.title = payload.title.strip()
    row.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(row)
    return {
        "id": row.id,
        "title": row.title,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


@app.get("/api/v1/conversations/{conversation_id}/messages")
async def messages(
    conversation_id: str,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    owned = await db.scalar(
        select(ConversationRow.id).where(
            ConversationRow.id == conversation_id, ConversationRow.user_id == principal.user_id
        )
    )
    if owned is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Conversation not found"})
    rows = (
        await db.scalars(
            select(MessageRow)
            .where(MessageRow.conversation_id == conversation_id)
            .order_by(MessageRow.created_at)
        )
    ).all()
    return {
        "items": [
            {"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at}
            for m in rows
        ]
    }


@app.delete("/api/v1/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    row = await db.scalar(
        select(ConversationRow).where(
            ConversationRow.id == conversation_id, ConversationRow.user_id == principal.user_id
        )
    )
    if row is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Conversation not found"})
    await db.delete(row)
    await db.commit()


@app.post("/api/v1/simulations")
async def simulations(payload: SimulationRequest, _: Principal = Depends(current_principal)):
    return simulate(payload)


class UploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(max_length=150)
    size_bytes: int = Field(gt=0)


@app.post("/api/v1/files/upload-url", status_code=201)
async def create_upload(
    payload: UploadRequest,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    from app.providers.storage import StorageUnavailable, presigned_upload

    if (
        payload.size_bytes > settings.upload_max_bytes
        or "/" in payload.filename
        or "\\" in payload.filename
    ):
        raise HTTPException(
            400, detail={"code": "invalid_file", "message": "Invalid filename or file size"}
        )
    row = FileRow(
        id=str(uuid.uuid4()),
        user_id=principal.user_id,
        filename=payload.filename,
        mime_type=payload.mime_type,
        size_bytes=payload.size_bytes,
    )
    try:
        url = presigned_upload(principal.user_id, row.id, payload.mime_type, payload.size_bytes)
    except StorageUnavailable as exc:
        raise HTTPException(
            503, detail={"code": "storage_unavailable", "message": str(exc)}
        ) from exc
    except ValueError as exc:
        raise HTTPException(400, detail={"code": "invalid_file", "message": str(exc)}) from exc
    db.add(row)
    await db.commit()
    return {"file_id": row.id, "upload_url": url, "expires_in": 300, "status": row.status}


@app.post("/api/v1/files", status_code=201)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    from app.jobs.worker import run_due_once
    from app.persistence.models import JobRow
    from app.services.files import (
        make_key,
        read_upload,
        safe_filename,
        storage_path,
        validate_bytes,
    )

    try:
        filename = safe_filename(file.filename or "")
        data = await read_upload(file)
        mime, ext = validate_bytes(filename, data)
        declared = (file.content_type or "").split(";")[0].lower()
        aliases = {
            "text/markdown": {"text/markdown", "text/plain"},
            "application/json": {"application/json", "text/json"},
            "text/csv": {"text/csv", "application/vnd.ms-excel"},
            "text/plain": {"text/plain"},
            "application/pdf": {"application/pdf"},
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            },
            "image/png": {"image/png"},
            "image/jpeg": {"image/jpeg"},
        }
        if declared and declared != "application/octet-stream" and declared not in aliases[mime]:
            raise ValueError("Declared MIME type does not match the file extension")
    except Exception as exc:
        # Parser diagnostics may contain internal paths or archive member names.
        message = (
            str(exc)
            if isinstance(exc, (ValueError, UnicodeDecodeError))
            else "Document processing failed; check that the file is valid and unencrypted"
        )
        raise HTTPException(400, detail={"code": "invalid_file", "message": message[:200]}) from exc
    key = make_key()
    path = storage_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

    is_image = ext in {".png", ".jpg", ".jpeg"}
    initial_status = "ready" if is_image else "processing"

    row = FileRow(
        id=key,
        user_id=principal.user_id,
        filename=filename,
        mime_type=mime,
        size_bytes=len(data),
        status=initial_status,
        storage_key=key,
    )
    db.add(row)

    if not is_image:
        job = JobRow(
            user_id=principal.user_id,
            job_type="document_ingestion",
            payload=json.dumps({"file_id": key}),
            scheduled_at=datetime.now(UTC),
            idempotency_key=f"doc_ingest:{key}",
            status="queued",
        )
        db.add(job)

    await db.commit()

    if not is_image:
        background_tasks.add_task(run_due_once, None, 25, "document_ingestion")

    return file_view(row)


def file_view(row: FileRow):
    return {
        "id": row.id,
        "filename": row.filename,
        "mime_type": row.mime_type,
        "size_bytes": row.size_bytes,
        "status": row.status,
        "error_message": row.error_message,
        "created_at": row.created_at,
        "download_available": row.status == "ready",
    }


@app.get("/api/v1/files/{file_id}/download")
async def download_file(
    file_id: str,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    from app.services.files import storage_path

    row = await db.scalar(
        select(FileRow).where(
            FileRow.id == file_id, FileRow.user_id == principal.user_id, FileRow.status == "ready"
        )
    )
    if row is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "File not found"})
    path = storage_path(row.storage_key)
    if not path.is_file():
        raise HTTPException(
            404, detail={"code": "object_missing", "message": "Stored file is unavailable"}
        )
    return FileResponse(path, media_type=row.mime_type, filename=row.filename)


@app.post("/api/v1/audio/transcriptions")
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str | None = Form(None, max_length=20, pattern=r"^[a-zA-Z-]+$"),
    _: Principal = Depends(current_principal),
):
    if settings.stt_provider == "disabled":
        raise HTTPException(
            503, detail={"code": "stt_disabled", "message": "Speech transcription is disabled"}
        )
    if (file.content_type or "").split(";")[0] not in {
        "audio/webm",
        "audio/wav",
        "audio/x-wav",
        "audio/mpeg",
        "audio/mp4",
        "audio/ogg",
    }:
        raise HTTPException(
            415,
            detail={
                "code": "unsupported_audio",
                "message": "Use WebM, WAV, MP3, MP4, or OGG audio",
            },
        )
    data = await file.read(settings.stt_max_bytes + 1)
    if not data or len(data) > settings.stt_max_bytes:
        raise HTTPException(
            400, detail={"code": "invalid_audio", "message": "Audio is empty or too large"}
        )
    mime = (file.content_type or "").split(";")[0]
    signatures = {
        "audio/webm": data.startswith(b"\x1aE\xdf\xa3"),
        "audio/wav": data.startswith(b"RIFF") and data[8:12] == b"WAVE",
        "audio/x-wav": data.startswith(b"RIFF") and data[8:12] == b"WAVE",
        "audio/mpeg": data.startswith(b"ID3")
        or (len(data) > 1 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0),
        "audio/mp4": b"ftyp" in data[:16],
        "audio/ogg": data.startswith(b"OggS"),
    }
    if not signatures.get(mime, False):
        raise HTTPException(
            415,
            detail={
                "code": "unsupported_audio",
                "message": "Audio content does not match a supported format",
            },
        )
    import asyncio
    import os
    import tempfile

    if importlib.util.find_spec("faster_whisper") is None:
        raise HTTPException(
            503,
            detail={
                "code": "stt_dependency_missing",
                "message": "Install the optional voice dependencies",
            },
        )
    try:
        with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as temp:
            temp.write(data)
            temp_path = temp.name
        model = _whisper_model()

        def transcribe():
            segment_iter, info = model.transcribe(temp_path, language=language)
            return list(segment_iter), info

        segments, info = await asyncio.wait_for(
            asyncio.to_thread(transcribe), settings.stt_timeout_seconds
        )
        if info.duration and info.duration > settings.stt_max_duration_seconds:
            raise HTTPException(
                413,
                detail={
                    "code": "audio_too_long",
                    "message": "Recording exceeds the duration limit",
                },
            )
        return {
            "text": " ".join(segment.text.strip() for segment in segments).strip(),
            "language": info.language,
            "duration_seconds": info.duration,
            "provider": settings.stt_provider,
            "model": settings.stt_model,
            "id": str(uuid.uuid4()),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            422,
            detail={"code": "transcription_failed", "message": "Audio could not be transcribed"},
        ) from exc
    finally:
        if "temp_path" in locals():
            os.unlink(temp_path)


@app.post("/api/v1/audio/speech")
async def speech(payload: dict, _: Principal = Depends(current_principal)):
    if settings.tts_provider == "disabled":
        raise HTTPException(
            503, detail={"code": "tts_disabled", "message": "Speech generation is disabled"}
        )
    from app.services.speech import speech_text

    raw_text = payload.get("text", "")
    if (
        not isinstance(raw_text, str)
        or not raw_text.strip()
        or len(raw_text) > settings.tts_max_chars
    ):
        raise HTTPException(
            400, detail={"code": "invalid_text", "message": "Text is empty or too long"}
        )
    text = speech_text(raw_text)
    voice = payload.get("voice", settings.tts_voice)
    if voice not in {"af_heart", "af_bella", "am_adam", "am_michael"}:
        raise HTTPException(
            422, detail={"code": "unsupported_voice", "message": "That voice is not supported"}
        )
    try:
        import importlib
        import io

        numpy = importlib.import_module("numpy")
        soundfile = importlib.import_module("soundfile")

        pipeline = _kokoro_pipeline()
        audio_parts = [audio for _, _, audio in pipeline(text, voice=voice)]
        buffer = io.BytesIO()
        soundfile.write(buffer, numpy.concatenate(audio_parts), 24000, format="WAV")
        from fastapi.responses import Response

        return Response(buffer.getvalue(), media_type="audio/wav")
    except ImportError as exc:
        raise HTTPException(
            503,
            detail={
                "code": "tts_dependency_missing",
                "message": "Install the optional voice dependencies",
            },
        ) from exc
    except Exception as exc:
        raise HTTPException(
            502, detail={"code": "synthesis_failed", "message": "Speech synthesis failed"}
        ) from exc


@app.post("/api/v1/files/{file_id}/complete")
async def complete_upload(
    file_id: str,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    row = await db.scalar(
        select(FileRow).where(FileRow.id == file_id, FileRow.user_id == principal.user_id)
    )
    if row is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "File not found"})
    row.status = "uploaded_unprocessed"
    await db.commit()
    return {
        "file_id": row.id,
        "status": row.status,
        "message": "Object upload registered; document extraction is not enabled in this build",
    }


@app.get("/api/v1/files")
async def list_files(
    principal: Principal = Depends(current_principal), db: AsyncSession = Depends(get_session)
):
    rows = (
        await db.scalars(
            select(FileRow)
            .where(FileRow.user_id == principal.user_id)
            .order_by(FileRow.created_at.desc())
            .limit(100)
        )
    ).all()
    return {
        "items": [
            {
                "id": f.id,
                "filename": f.filename,
                "mime_type": f.mime_type,
                "size_bytes": f.size_bytes,
                "status": f.status,
                "created_at": f.created_at,
                "download_available": f.status == "ready",
                "error_message": f.error_message,
            }
            for f in rows
        ]
    }


@app.get("/api/v1/files/{file_id}")
async def get_file(
    file_id: str,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    row = await db.scalar(
        select(FileRow).where(FileRow.id == file_id, FileRow.user_id == principal.user_id)
    )
    if row is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "File not found"})
    return {
        "id": row.id,
        "filename": row.filename,
        "mime_type": row.mime_type,
        "size_bytes": row.size_bytes,
        "status": row.status,
        "created_at": row.created_at,
        "download_available": row.status == "ready",
        "error_message": row.error_message,
    }


@app.delete("/api/v1/files/{file_id}", status_code=204)
async def delete_file(
    file_id: str,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    row = await db.scalar(
        select(FileRow).where(FileRow.id == file_id, FileRow.user_id == principal.user_id)
    )
    if row is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "File not found"})
    from app.services.files import storage_path

    if row.storage_key:
        storage_path(row.storage_key).unlink(missing_ok=True)
    await db.delete(row)
    await db.commit()


class ResearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1000)


@app.post("/api/v1/research")
async def research_endpoint(payload: ResearchRequest, _: Principal = Depends(current_principal)):
    from app.providers.research import ResearchUnavailable, research

    try:
        return {"query": payload.query, "sources": await research(payload.query), "live": True}
    except ResearchUnavailable as exc:
        raise HTTPException(
            503, detail={"code": "research_unavailable", "message": str(exc)}
        ) from exc


class Feedback(BaseModel):
    conversation_id: str | None = None
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)


@app.post("/api/v1/feedback", status_code=201)
async def feedback(
    payload: Feedback,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    if payload.conversation_id:
        owned = await db.scalar(
            select(ConversationRow.id).where(
                ConversationRow.id == payload.conversation_id,
                ConversationRow.user_id == principal.user_id,
            )
        )
        if not owned:
            raise HTTPException(
                404, detail={"code": "not_found", "message": "Conversation not found"}
            )
    row = FeedbackRow(user_id=principal.user_id, **payload.model_dump())
    db.add(row)
    await db.commit()
    return {"status": "recorded"}


@app.get("/api/v1/admin/traces")
async def list_admin_traces(
    limit: int = 50,
    offset: int = 0,
    search: str | None = None,
    tool_filter: str | None = None,
    status: str | None = None,
    _: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    items = await get_traces(
        db=db,
        limit=limit,
        offset=offset,
        search=search,
        tool_filter=tool_filter,
        status_filter=status,
    )
    return {"items": items}


@app.get("/api/v1/admin/traces/{trace_id}")
async def get_admin_trace(
    trace_id: str,
    _: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    item = await get_trace_by_id(trace_id, db=db)
    if not item:
        raise HTTPException(404, detail={"code": "not_found", "message": "Trace not found"})
    return item


@app.delete("/api/v1/admin/traces", status_code=204)
async def clear_admin_traces(
    _: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    await clear_traces(db=db)


@app.get("/api/v1/admin/stats")
async def admin_stats(
    _: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    return await get_stats(db=db)
