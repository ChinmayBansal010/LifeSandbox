import json
import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models import MemoryPolicyRow, MemoryRow

SENSITIVE_CATEGORIES = {"health", "financial", "identity", "credential"}


def tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{3,}", value.lower()))


async def policy_for(db: AsyncSession, user_id: str) -> MemoryPolicyRow:
    policy = await db.get(MemoryPolicyRow, user_id)
    if policy is None:
        policy = MemoryPolicyRow(user_id=user_id)
        db.add(policy)
        await db.flush()
    return policy


async def search_memories(db: AsyncSession, user_id: str, query: str, limit: int = 5):
    policy = await policy_for(db, user_id)
    if not policy.enabled:
        return []
    rows = (
        await db.scalars(
            select(MemoryRow).where(MemoryRow.user_id == user_id, MemoryRow.status == "active")
        )
    ).all()
    query_terms = tokens(query)
    ranked = []
    now = datetime.now(UTC)
    for row in rows:
        terms = tokens(row.content)
        overlap = len(query_terms & terms)
        if overlap:
            age_days = max(0, (now - row.created_at.replace(tzinfo=UTC)).days)
            score = (
                overlap / max(len(query_terms), 1) + min(row.confidence, 1) * 0.1 - age_days / 3650
            )
            ranked.append((score, row))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return [row for _, row in ranked[:limit]]


async def save_memory(
    db: AsyncSession,
    user_id: str,
    content: str,
    category: str,
    *,
    consent: bool,
    source: str = "user-approved",
    source_conversation_id: str | None = None,
):
    if not consent:
        raise ValueError("Explicit consent is required to retain a memory")
    policy = await policy_for(db, user_id)
    if not policy.enabled:
        raise ValueError("Memory is disabled in your memory policy")
    content = content.strip()
    if not content or re.search(r"(?i)(sk-or-v1-|api[_ -]?key|secret|password)\s*[:=]", content):
        raise ValueError("Empty content or credentials cannot be saved as memory")
    key = f"{category}:{' '.join(sorted(tokens(content)))}"
    existing = await db.scalar(
        select(MemoryRow).where(
            MemoryRow.user_id == user_id,
            MemoryRow.identity_key == key,
            MemoryRow.status == "active",
        )
    )
    if existing:
        existing.status = "superseded"
    row = MemoryRow(
        user_id=user_id,
        content=content,
        category=category,
        source=source,
        source_conversation_id=source_conversation_id,
        identity_key=key,
        status="active",
    )
    db.add(row)
    await db.flush()
    return row


async def apply_retention(db: AsyncSession, policy: MemoryPolicyRow):
    if policy.retention_days:
        cutoff = datetime.now(UTC) - timedelta(days=policy.retention_days)
        rows = (
            await db.scalars(
                select(MemoryRow).where(
                    MemoryRow.user_id == policy.user_id,
                    MemoryRow.status == "active",
                    MemoryRow.created_at < cutoff,
                )
            )
        ).all()
        for row in rows:
            row.status = "archived"


def policy_json(policy: MemoryPolicyRow):
    return {
        "enabled": policy.enabled,
        "auto_categories": json.loads(policy.auto_categories),
        "approval_categories": json.loads(policy.approval_categories),
        "never_auto_categories": json.loads(policy.never_auto_categories),
        "retention_days": policy.retention_days,
        "hosted_memory_allowed": policy.hosted_memory_allowed,
    }
