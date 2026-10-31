import asyncio
import base64
import json
import logging
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversation.graph import conversation_graph
from app.core.config import get_settings
from app.memory.service import (
    policy_for,
    process_explicit_memory_request,
    search_conversation_history,
    search_memories,
)
from app.persistence.models import (
    ConversationFileRow,
    ConversationRow,
    FileChunkRow,
    FileRow,
    JobRow,
    MessageRow,
)
from app.providers.mem0 import remember_exchange
from app.providers.mem0 import search_memories as search_hosted_memories
from app.rag.embeddings import cosine, embed
from app.services.files import storage_path
from app.services.tool_tracker import trace_prompt, trace_tool


async def run_chat(
    db: AsyncSession,
    user_id: str,
    message: str,
    conversation_id: str | None = None,
    history_override: list[dict[str, str]] | None = None,
    remember: bool = False,
    browse: bool = False,
    is_disconnected=None,
    attachment_ids: list[str] | None = None,
    channel: str = "web",
):
    if conversation_id:
        row = await db.scalar(
            select(ConversationRow).where(ConversationRow.id == conversation_id, ConversationRow.user_id == user_id)
        )
        if row is None:
            existing = await db.scalar(select(ConversationRow.id).where(ConversationRow.id == conversation_id))
            if existing is not None:
                return None
            row = ConversationRow(
                id=conversation_id,
                user_id=user_id,
                title=message[:80].strip() or "New conversation",
            )
            db.add(row)
            await db.flush()
        else:
            if row.title in {"New conversation", "New chat", ""} and message.strip():
                row.title = message[:80].strip()
            row.updated_at = datetime.now(UTC)
    else:
        row = ConversationRow(id=str(uuid4()), user_id=user_id, title=message[:80])
        db.add(row)
        await db.flush()

    history_rows = (
        await db.scalars(
            select(MessageRow)
            .where(MessageRow.conversation_id == row.id)
            .order_by(MessageRow.created_at.desc())
            .limit(12)
        )
    ).all()
    history_rows = list(reversed(history_rows))
    # Persisted messages are authoritative. Client-provided history can be stale,
    # truncated, or empty after a reload, which otherwise makes the chat forget.
    history = [{"role": m.role, "content": m.content} for m in history_rows]

    file_context = ""
    image_inputs: list[dict[str, str]] = []
    if attachment_ids or conversation_id:
        previous_file_ids = list(
            (
                await db.scalars(
                    select(ConversationFileRow.file_id)
                    .where(
                        ConversationFileRow.conversation_id == row.id,
                        ConversationFileRow.user_id == user_id,
                    )
                    .order_by(ConversationFileRow.created_at.desc())
                    .limit(5)
                )
            ).all()
        )
        requested_file_ids = list(dict.fromkeys(attachment_ids or []))
        retained_file_ids = list(dict.fromkeys(requested_file_ids + previous_file_ids))[:5]
        files = list(
            (
                await db.scalars(
                    select(FileRow).where(
                        FileRow.id.in_(retained_file_ids),
                        FileRow.user_id == user_id,
                        FileRow.status == "ready",
                    )
                )
            ).all()
        )
        available_file_ids = {file.id for file in files}
        if not set(requested_file_ids).issubset(available_file_ids):
            raise ValueError("One or more attached files are unavailable or not ready")
        known_file_ids = available_file_ids
        for file_id in requested_file_ids:
            if not await db.scalar(
                select(ConversationFileRow.id).where(
                    ConversationFileRow.conversation_id == row.id,
                    ConversationFileRow.file_id == file_id,
                    ConversationFileRow.user_id == user_id,
                )
            ):
                db.add(ConversationFileRow(conversation_id=row.id, file_id=file_id, user_id=user_id))
        query_vec = embed(message)
        dialect_name = getattr(db.bind, "dialect", None)
        dialect = getattr(dialect_name, "name", "") if dialect_name else ""
        top_chunks = []
        if dialect == "postgresql":
            try:
                top_chunks = list(
                    (
                        await db.scalars(
                            select(FileChunkRow)
                            .where(
                                FileChunkRow.file_id.in_(known_file_ids),
                                FileChunkRow.user_id == user_id,
                                FileChunkRow.embedding.is_not(None),
                            )
                            .order_by(FileChunkRow.embedding.cosine_distance(query_vec))
                            .limit(5)
                        )
                    ).all()
                )
            except Exception:
                top_chunks = []
        if not top_chunks:
            all_candidate_chunks = list(
                (
                    await db.scalars(
                        select(FileChunkRow).where(
                            FileChunkRow.file_id.in_(known_file_ids),
                            FileChunkRow.user_id == user_id,
                        )
                    )
                ).all()
            )
            if all_candidate_chunks:
                top_chunks = sorted(
                    all_candidate_chunks,
                    key=lambda c: cosine(
                        query_vec,
                        c.embedding if c.embedding is not None else embed(c.content),
                    ),
                    reverse=True,
                )[:5]

        image_files = [file for file in files if file.mime_type in {"image/png", "image/jpeg"}]
        settings = get_settings()
        if image_files and (not settings.vision_enabled or settings.llm_provider == "mock"):
            raise ValueError(
                "Image understanding is disabled; configure a vision-capable model and enable VISION_ENABLED"
            )
        total_image_bytes = 0
        for image_file in image_files:
            image_path = storage_path(image_file.storage_key)
            if not image_path.is_file():
                raise ValueError(f"Attached image is unavailable: {image_file.filename}")
            image_bytes = image_path.read_bytes()
            total_image_bytes += len(image_bytes)
            if total_image_bytes > get_settings().image_max_bytes:
                raise ValueError("Attached images exceed the combined context size limit")
            image_inputs.append(
                {
                    "filename": image_file.filename,
                    "mime_type": image_file.mime_type,
                    "data": base64.b64encode(image_bytes).decode("ascii"),
                }
            )
        excerpts = []
        for chunk in top_chunks:
            file_row = next((item for item in files if item.id == chunk.file_id), None)
            if not file_row:
                continue
            pos = f", page {chunk.page_number}" if chunk.page_number else ""
            excerpts.append(f"[{file_row.filename}{pos}]\n{chunk.content}")
        if requested_file_ids and not excerpts and not image_inputs:
            raise ValueError("Attached files have no extracted text")
        file_context = "\n\n".join(excerpts)

    async with trace_prompt(
        prompt=message,
        user_id=user_id,
        conversation_id=row.id,
        db=db,
    ) as trace_data:
        memories = []
        past_conversations = []
        hosted_search_status = "not_requested"
        try:
            # Isolate optional memory-store failures so they do not poison the
            # conversation transaction and fail after the model has responded.
            async with db.begin_nested():
                recalled = await search_memories(db, user_id, message)
            memories = [f"[{item.category}; source={item.source}] {item.content}" for item in recalled]
        except Exception:
            logging.getLogger("life_sandbox.memory").exception("Local memory retrieval failed")
        try:
            async with db.begin_nested():
                past_conversations = await search_conversation_history(db, user_id, row.id, message)
        except Exception:
            logging.getLogger("life_sandbox.memory").exception("Local conversation recall failed")
        if remember:
            hosted_allowed = False
            try:
                async with db.begin_nested():
                    policy = await policy_for(db, user_id)
                    # The per-message switch is explicit consent for this exchange.
                    # Keep the global memory policy as the user's master off switch.
                    hosted_allowed = policy.enabled and policy.hosted_memory_allowed
            except Exception:
                logging.getLogger("life_sandbox.memory").exception("Memory policy lookup failed")
            if hosted_allowed:
                hosted_search_status = "succeeded"
                async with trace_tool("mem0_search", "memory", {"user_id": user_id}) as mem_event:
                    try:
                        memories.extend(await search_hosted_memories(message, user_id))
                        mem_event["output_data"] = {"count": len(memories)}
                    except Exception as exc:
                        hosted_search_status = (
                            "timed_out" if isinstance(exc, (TimeoutError, asyncio.TimeoutError)) else "failed"
                        )
                        logging.getLogger("life_sandbox.mem0").warning(
                            "provider_call_failed provider=mem0 stage=mem0_search outcome=%s",
                            "timeout" if isinstance(exc, (TimeoutError, asyncio.TimeoutError)) else "upstream_error",
                        )
                        mem_event["status"] = "error"
                        mem_event["error"] = "provider call failed"
            else:
                hosted_search_status = "disabled"

        db.add(MessageRow(conversation_id=row.id, role="user", content=message))
        try:
            model_task = asyncio.create_task(
                conversation_graph.ainvoke(
                    {
                        "user_id": user_id,
                        "conversation_id": row.id,
                        "message": message,
                        "history": history,
                        "memories": memories,
                        "past_conversations": past_conversations,
                        "file_context": file_context,
                        "image_inputs": image_inputs,
                        "allow_browser_use": browse,
                        "channel": channel,
                        "db": db,
                    }
                )
            )
            if is_disconnected is not None:
                disconnect_task = asyncio.create_task(is_disconnected())
                done, _ = await asyncio.wait(
                    [model_task, disconnect_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if disconnect_task in done and not disconnect_task.cancelled() and disconnect_task.result():
                    model_task.cancel()
                    await asyncio.gather(model_task, return_exceptions=True)
                    logging.getLogger("life_sandbox.chat").info(
                        "chat_turn_cancelled provider=openrouter stage=client_disconnect outcome=cancelled"
                    )
                    raise asyncio.CancelledError
                if not disconnect_task.done():
                    disconnect_task.cancel()
            state = await model_task
        except Exception:
            await db.rollback()
            raise

        memory_request = None
        try:
            async with db.begin_nested():
                memory_request = await process_explicit_memory_request(db, user_id, message, row.id)
        except Exception:
            logging.getLogger("life_sandbox.memory").exception("Explicit memory request processing failed")

        db.add(MessageRow(conversation_id=row.id, role="assistant", content=state["reply"]))
        row.updated_at = datetime.now(UTC)
        await db.commit()

        memory_saved = False
        mem0_search_status = hosted_search_status
        mem0_save_status = "not_requested" if not remember else ("not_attempted" if hosted_allowed else "disabled")
        failure_detail = None
        if mem0_search_status in {"failed", "timed_out"}:
            failure_detail = {
                "provider": "mem0",
                "stage": "mem0_search",
                "code": "timeout" if mem0_search_status == "timed_out" else "upstream_error",
                "message": ("Mem0 search failed; this reply was generated without recalled memories."),
                "retriable": True,
            }
        if remember and hosted_allowed:
            async with trace_tool("mem0_save", "memory", {"user_id": user_id}) as save_event:
                try:
                    await remember_exchange(user_id, message, state["reply"])
                    memory_saved = True
                    mem0_save_status = "saved"
                    save_event["output_data"] = {"saved": True}
                except Exception as exc:
                    mem0_save_status = (
                        "timed_out" if isinstance(exc, (TimeoutError, asyncio.TimeoutError)) else "failed"
                    )
                    failure_detail = {
                        "provider": "mem0",
                        "stage": "mem0_add",
                        "code": "timeout" if mem0_save_status == "timed_out" else "upstream_error",
                        "message": ("The reply was generated, but Mem0 could not confirm saving this exchange."),
                        "retriable": True,
                    }
                    logging.getLogger("life_sandbox.mem0").warning(
                        "provider_call_failed provider=mem0 stage=mem0_add outcome=%s",
                        mem0_save_status,
                    )
                    save_event["status"] = "error"
                    save_event["error"] = str(exc)

        await db.refresh(row)
        # Asynchronous memory reflection job without requiring explicit 'remember' syntax
        reflection_job = JobRow(
            user_id=user_id,
            job_type="memory_reflection",
            payload=json.dumps(
                {
                    "conversation_id": row.id,
                    "message": message,
                    "reply": state.get("reply", ""),
                }
            ),
            scheduled_at=datetime.now(UTC),
            idempotency_key=f"reflect:{row.id}:{uuid4()}",
            status="queued",
        )
        db.add(reflection_job)
        await db.commit()

        trace_data["response_preview"] = state["reply"][:500]
        trace_data["skill"] = state.get("skill")
        trace_data["skill_trigger"] = state.get("skill_trigger")
        trace_data["intent"] = state.get("intent")

        return {
            "conversation_id": row.id,
            "reply": state["reply"],
            "intent": state["intent"],
            "skill": state.get("skill"),
            "skill_trigger": state.get("skill_trigger"),
            "provider": state["provider"],
            "model": state.get("model"),
            "memory_saved": memory_saved,
            "mem0_opt_in": remember,
            "mem0_search_status": mem0_search_status,
            "mem0_save_status": mem0_save_status,
            "failure_detail": failure_detail,
            "memory_request": memory_request,
            "trace_id": trace_data.get("id"),
            "tools_accessed": trace_data.get("tools_accessed", []),
        }
