import json
import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models import MemoryCandidateRow, MemoryPolicyRow, MemoryRow

SENSITIVE_CATEGORIES = {"health", "financial", "identity", "credential"}


def tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{3,}", value.lower()))


def identity_key_for(category: str, content: str) -> str:
    normalized = re.sub(r"[^a-z0-9 ]", " ", content.lower())
    normalized = " ".join(normalized.split())
    predicate = re.search(
        r"\b(?:prefer|likes?|dislikes?|avoid|wants?|needs?|am|is|are|uses?|works?)\b",
        normalized,
    )
    identity = normalized[: predicate.end()] if predicate else " ".join(sorted(tokens(content)))
    return f"{category}:{identity[:180]}"


def explicit_memory_request(message: str) -> tuple[str, str] | None:
    match = re.search(r"\bremember(?:\s+that|\s*:)?\s+(.+)", message, re.IGNORECASE)
    if match is None:
        return None
    content = match.group(1).splitlines()[0].strip(" \t.!?")
    if not content or len(content) > 2000:
        return None
    lowered = content.lower()
    if re.search(
        r"\b(?:api[ _-]?key|password|passphrase|secret|credential|access token|bearer token)\b|"
        r"sk-or-v1-[a-z0-9_-]+",
        lowered,
    ):
        return None
    if any(term in lowered for term in ("health", "diagnosis", "medication", "allergy")):
        category = "health"
    elif any(term in lowered for term in ("bank account", "income", "salary", "debt")):
        category = "financial"
    elif any(term in lowered for term in ("prefer", "like", "dislike", "avoid")):
        category = "preference"
    elif "project" in lowered:
        category = "project"
    elif any(term in lowered for term in ("last year", "yesterday", "i decided", "i learned")):
        category = "episode"
    else:
        category = "profile"
    return category, content


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
    await apply_retention(db, policy)
    rows = (
        await db.scalars(
            select(MemoryRow)
            .where(MemoryRow.user_id == user_id, MemoryRow.status == "active")
            .order_by(MemoryRow.updated_at.desc())
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
    project_id: str | None = None,
):
    if not consent:
        raise ValueError("Explicit consent is required to retain a memory")
    policy = await policy_for(db, user_id)
    if not policy.enabled:
        raise ValueError("Memory is disabled in your memory policy")
    content = content.strip()
    if not content or re.search(r"(?i)(sk-or-v1-|api[_ -]?key|secret|password)\s*[:=]", content):
        raise ValueError("Empty content or credentials cannot be saved as memory")
    key = identity_key_for(category, content)
    existing = await db.scalar(
        select(MemoryRow).where(
            MemoryRow.user_id == user_id,
            MemoryRow.identity_key == key,
            MemoryRow.status == "active",
        )
    )
    if existing:
        if existing.content.casefold() == content.casefold():
            existing.updated_at = datetime.now(UTC)
            return existing
        existing.status = "superseded"
    row = MemoryRow(
        user_id=user_id,
        content=content,
        category=category,
        source=source,
        source_conversation_id=source_conversation_id,
        project_id=project_id,
        identity_key=key,
        status="active",
    )
    db.add(row)
    await db.flush()
    return row


async def process_explicit_memory_request(
    db: AsyncSession, user_id: str, message: str, conversation_id: str
):
    extracted = explicit_memory_request(message)
    if extracted is None:
        return None
    category, content = extracted
    policy = await policy_for(db, user_id)
    if not policy.enabled:
        return None
    auto_categories = set(json.loads(policy.auto_categories))
    approval_categories = set(json.loads(policy.approval_categories))
    never_auto = set(json.loads(policy.never_auto_categories))
    if (
        category in auto_categories
        and category not in never_auto
        and category not in SENSITIVE_CATEGORIES
    ):
        row = await save_memory(
            db,
            user_id,
            content,
            category,
            consent=True,
            source="explicit-chat-request",
            source_conversation_id=conversation_id,
        )
        return {"status": "saved", "id": row.id}
    if category not in approval_categories and category not in never_auto:
        return None
    pending = await db.scalar(
        select(MemoryCandidateRow).where(
            MemoryCandidateRow.user_id == user_id,
            MemoryCandidateRow.category == category,
            MemoryCandidateRow.content == content,
            MemoryCandidateRow.status == "pending",
        )
    )
    if pending:
        return {"status": "pending", "id": pending.id}
    candidate = MemoryCandidateRow(
        user_id=user_id,
        content=content,
        category=category,
        source_conversation_id=conversation_id,
    )
    db.add(candidate)
    await db.flush()
    return {"status": "pending", "id": candidate.id}


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
