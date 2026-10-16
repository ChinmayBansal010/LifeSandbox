import logging
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversation.graph import conversation_graph
from app.persistence.models import ConversationRow, MessageRow
from app.providers.mem0 import remember_exchange, search_memories
from app.services.tool_tracker import trace_prompt, trace_tool


async def run_chat(
    db: AsyncSession,
    user_id: str,
    message: str,
    conversation_id: str | None = None,
    history_override: list[dict[str, str]] | None = None,
    remember: bool = False,
    browse: bool = False,
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
    history = history_override if history_override is not None else [
        {"role": m.role, "content": m.content} for m in history_rows
    ]

    async with trace_prompt(
        prompt=message,
        user_id=user_id,
        conversation_id=row.id,
        db=db,
    ) as trace_data:
        memories = []
        if remember:
            async with trace_tool("mem0_search", "memory", {"query": message, "user_id": user_id}) as mem_event:
                try:
                    memories = await search_memories(message, user_id)
                    mem_event["output_data"] = {"count": len(memories), "memories": memories[:3]}
                except Exception as exc:
                    logging.getLogger("life_sandbox.mem0").exception("Mem0 memory search failed")
                    mem_event["status"] = "error"
                    mem_event["error"] = str(exc)

        db.add(MessageRow(conversation_id=row.id, role="user", content=message))
        try:
            state = await conversation_graph.ainvoke(
                {
                    "user_id": user_id,
                    "conversation_id": row.id,
                    "message": message,
                    "history": history,
                    "memories": memories,
                    "allow_browser_use": browse,
                }
            )
        except Exception:
            await db.rollback()
            raise

        db.add(MessageRow(conversation_id=row.id, role="assistant", content=state["reply"]))
        await db.commit()

        memory_saved = False
        if remember:
            async with trace_tool("mem0_save", "memory", {"user_id": user_id}) as save_event:
                try:
                    await remember_exchange(user_id, message, state["reply"])
                    memory_saved = True
                    save_event["output_data"] = {"saved": True}
                except Exception as exc:
                    logging.getLogger("life_sandbox.mem0").exception("Mem0 memory write failed")
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
            "trace_id": trace_data.get("id"),
            "tools_accessed": trace_data.get("tools_accessed", []),
        }

