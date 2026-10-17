import logging
import asyncio
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversation.graph import conversation_graph
from app.memory.service import (
    policy_for,
    process_explicit_memory_request,
    search_memories,
)
from app.persistence.models import ConversationRow, MessageRow
from app.providers.mem0 import remember_exchange
from app.providers.mem0 import search_memories as search_hosted_memories
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
):
    if conversation_id:
        row = await db.scalar(
            select(ConversationRow).where(
                ConversationRow.id == conversation_id, ConversationRow.user_id == user_id
            )
        )
        if row is None:
            return None
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
    history = (
        history_override
        if history_override is not None
        else [{"role": m.role, "content": m.content} for m in history_rows]
    )

    async with trace_prompt(
        prompt=message,
        user_id=user_id,
        conversation_id=row.id,
        db=db,
    ) as trace_data:
        memories = []
        hosted_search_status = "not_requested"
        try:
            # Isolate optional memory-store failures so they do not poison the
            # conversation transaction and fail after the model has responded.
            async with db.begin_nested():
                recalled = await search_memories(db, user_id, message)
            memories = [
                f"[{item.category}; source={item.source}] {item.content}" for item in recalled
            ]
        except Exception:
            logging.getLogger("life_sandbox.memory").exception("Local memory retrieval failed")
        if remember:
            hosted_allowed = False
            try:
                async with db.begin_nested():
                    policy = await policy_for(db, user_id)
                    # The per-message switch is explicit consent for this exchange.
                    # Keep the global memory policy as the user's master off switch.
                    hosted_allowed = policy.enabled
            except Exception:
                logging.getLogger("life_sandbox.memory").exception("Memory policy lookup failed")
            if hosted_allowed:
                hosted_search_status = "succeeded"
                async with trace_tool("mem0_search", "memory", {"user_id": user_id}) as mem_event:
                    try:
                        memories.extend(await search_hosted_memories(message, user_id))
                        mem_event["output_data"] = {"count": len(memories)}
                    except Exception as exc:
                        hosted_search_status = "timed_out" if isinstance(exc, (TimeoutError, asyncio.TimeoutError)) else "failed"
                        logging.getLogger("life_sandbox.mem0").warning("provider_call_failed provider=mem0 stage=mem0_search outcome=%s", "timeout" if isinstance(exc, (TimeoutError, asyncio.TimeoutError)) else "upstream_error")
                        mem_event["status"] = "error"
                        mem_event["error"] = "provider call failed"

        db.add(MessageRow(conversation_id=row.id, role="user", content=message))
        try:
            model_task = asyncio.create_task(conversation_graph.ainvoke(
                {
                    "user_id": user_id,
                    "conversation_id": row.id,
                    "message": message,
                    "history": history,
                    "memories": memories,
                    "allow_browser_use": browse,
                    "db": db,
                }
            ))
            if is_disconnected is not None:
                while not model_task.done():
                    if await is_disconnected():
                        model_task.cancel()
                        await asyncio.gather(model_task, return_exceptions=True)
                        logging.getLogger("life_sandbox.chat").info("chat_turn_cancelled provider=openrouter stage=client_disconnect outcome=cancelled")
                        raise asyncio.CancelledError
                    await asyncio.sleep(0.2)
            state = await model_task
        except Exception:
            await db.rollback()
            raise

        memory_request = None
        try:
            async with db.begin_nested():
                memory_request = await process_explicit_memory_request(db, user_id, message, row.id)
        except Exception:
            logging.getLogger("life_sandbox.memory").exception(
                "Explicit memory request processing failed"
            )

        db.add(MessageRow(conversation_id=row.id, role="assistant", content=state["reply"]))
        await db.commit()

        memory_saved = False
        mem0_search_status = hosted_search_status
        mem0_save_status = "not_requested" if not remember else "not_attempted"
        failure_detail = None
        if mem0_search_status in {"failed", "timed_out"}:
            failure_detail = {
                "provider": "mem0", "stage": "mem0_search",
                "code": "timeout" if mem0_search_status == "timed_out" else "upstream_error",
                "message": "Mem0 search failed; this reply was generated without recalled memories.",
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
                    mem0_save_status = "timed_out" if isinstance(exc, (TimeoutError, asyncio.TimeoutError)) else "failed"
                    failure_detail = {
                        "provider": "mem0", "stage": "mem0_add",
                        "code": "timeout" if mem0_save_status == "timed_out" else "upstream_error",
                        "message": "The reply was generated, but Mem0 could not confirm saving this exchange.",
                        "retriable": True,
                    }
                    logging.getLogger("life_sandbox.mem0").warning("provider_call_failed provider=mem0 stage=mem0_add outcome=%s", mem0_save_status)
                    save_event["status"] = "error"
                    save_event["error"] = str(exc)

        await db.refresh(row)
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
