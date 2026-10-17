import logging
import uuid
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.life import router as life_router
from app.api.memory import router as memory_router
from app.api.workflow import router as workflow_router
from app.core.config import get_settings
from app.core.security import Principal, current_principal
from app.domain.simulation import SimulationRequest, simulate
from app.persistence.models import (
    Base,
    ConversationRow,
    FeedbackRow,
    FileRow,
    MessageRow,
)
from app.persistence.session import engine, get_session
from app.providers.browser_use import is_configured as browser_use_is_configured
from app.providers.llm import LLMError
from app.providers.mem0 import is_configured as mem0_is_configured
from app.services.chat import run_chat
from app.services.tool_tracker import clear_traces, get_stats, get_trace_by_id, get_traces

settings = get_settings()
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
    yield
    await engine.dispose()


app = FastAPI(title="Life Sandbox API", version="0.1.0", lifespan=lifespan)
app.include_router(life_router)
app.include_router(memory_router)
app.include_router(workflow_router)
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


@app.get("/api/v1/capabilities")
async def capabilities():
    return {
        "mem0_enabled": mem0_is_configured(),
        "browser_use_enabled": browser_use_is_configured(),
    }


@app.get("/api/v1/skills")
async def list_skills():
    from app.skills.registry import get_all_skills_data
    return {"skills": get_all_skills_data()}



@app.post("/api/v1/chat")
async def chat(
    payload: ChatRequest,
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
    result = await run_chat(
        db,
        principal.user_id,
        payload.message,
        payload.conversation_id,
        payload.history,
        payload.remember,
        payload.browse,
    )
    if result is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Conversation not found"})
    return result


@app.post("/api/v1/chat/stream")
async def chat_stream(
    payload: ChatRequest,
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
