from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversation.graph import conversation_graph
from app.persistence.models import ConversationRow, MessageRow


async def run_chat(
    db: AsyncSession, user_id: str, message: str, conversation_id: str | None = None
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
    db.add(MessageRow(conversation_id=row.id, role="user", content=message))
    try:
        state = await conversation_graph.ainvoke(
            {
                "user_id": user_id,
                "conversation_id": row.id,
                "message": message,
                "history": [{"role": m.role, "content": m.content} for m in history_rows],
            }
        )
    except Exception:
        await db.rollback()
        raise
    db.add(MessageRow(conversation_id=row.id, role="assistant", content=state["reply"]))
    await db.commit()
    await db.refresh(row)
    return {
        "conversation_id": row.id,
        "reply": state["reply"],
        "intent": state["intent"],
        "skill": state.get("skill"),
        "provider": state["provider"],
        "model": state.get("model"),
    }
