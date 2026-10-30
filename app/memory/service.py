import json
import logging
import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models import (
    ConversationRow,
    MemoryCandidateRow,
    MemoryPolicyRow,
    MemoryRow,
    MessageRow,
)
from app.rag.embeddings import cosine, embed
from app.rag.retrieval import reciprocal_rank_fusion

logger = logging.getLogger("life_sandbox.memory")

_HISTORY_STOP_WORDS = {
    "about", "after", "again", "and", "are", "but", "can", "did", "does", "for",
    "from", "have", "how", "into", "last", "like", "mention", "more", "much", "please",
    "remember", "said", "that", "the", "then", "there", "this", "time", "talk", "talked",
    "tell", "them", "they", "what", "when", "where", "which", "who", "with", "would",
    "you", "your", "conversation", "chat", "discuss", "discussed", "earlier", "previous",
}


async def search_conversation_history(
    db: AsyncSession,
    user_id: str,
    current_conversation_id: str,
    query: str,
    limit: int = 4,
) -> list[str]:
    """Recall relevant user/assistant turns from this owner's earlier conversations."""
    policy = await policy_for(db, user_id)
    if not policy.enabled:
        return []

    query_terms = tokens(query) - _HISTORY_STOP_WORDS
    broad_recall = bool(
        re.search(
            r"\b(last time|previous conversation|earlier conversation|what did we (?:discuss|talk about)|"
            r"what (?:was|did) (?:my )?last (?:message|chat)|remember when|we talked about)\b",
            query.lower(),
        )
    )
    statement = (
        select(
            MessageRow.id,
            MessageRow.conversation_id,
            func.substr(MessageRow.content, 1, 2000),
            MessageRow.created_at,
            ConversationRow.title,
        )
        .join(ConversationRow, ConversationRow.id == MessageRow.conversation_id)
        .where(
            ConversationRow.user_id == user_id,
            ConversationRow.id != current_conversation_id,
            MessageRow.role == "user",
        )
        .order_by(MessageRow.created_at.desc())
        .limit(1000)
    )
    candidates = list((await db.execute(statement)).all())
    scored = []
    for row in candidates:
        content = row[2] or ""
        terms = tokens(content) - _HISTORY_STOP_WORDS
        overlap = query_terms & terms
        if overlap:
            score = len(overlap) / max(len(query_terms), 1) + 0.2 * len(overlap) / max(len(terms), 1)
            scored.append((score, row))
    scored.sort(key=lambda item: (item[0], item[1][3]), reverse=True)

    if scored:
        selected = [row for score, row in scored if score > 0][:limit]
    elif broad_recall:
        selected = candidates[:limit]
    else:
        return []

    recalled = []
    for row in selected:
        user_message_id, conversation_id, user_text, created_at, title = row
        assistant_text = await db.scalar(
            select(func.substr(MessageRow.content, 1, 2000))
            .where(
                MessageRow.conversation_id == conversation_id,
                MessageRow.role == "assistant",
                MessageRow.created_at >= created_at,
            )
            .order_by(MessageRow.created_at.asc())
            .limit(1)
        )
        date = created_at.strftime("%B %d, %Y") if created_at else "past"
        recalled.append(
            f"[Earlier context: {title or 'Earlier conversation'}; {date}]\n"
            f"User: {user_text}\nAssistant: {assistant_text or '(no saved reply)'}"
        )
    return recalled

SENSITIVE_CATEGORIES = {"health", "financial", "identity", "credential"}


def tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{3,}", value.lower()))


_IDENTITY_MODIFIERS = {
    "concise", "detailed", "short", "long", "brief", "verbose",
    "dark", "light", "fast", "slow", "simple", "complex",
    "more", "less", "high", "low", "morning", "evening",
}


def identity_key_for(category: str, content: str) -> str:
    normalized = re.sub(r"[^a-z0-9 ]", " ", content.lower())
    words = [w for w in normalized.split() if w not in _IDENTITY_MODIFIERS]
    identity = " ".join(words) if words else normalized
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
    rows = list(
        (
            await db.scalars(
                select(MemoryRow)
                .where(MemoryRow.user_id == user_id, MemoryRow.status == "active")
                .order_by(MemoryRow.updated_at.desc())
            )
        ).all()
    )
    if not rows:
        return []

    query_vec = embed(query)
    dialect_name = getattr(db.bind, "dialect", None)
    dialect = getattr(dialect_name, "name", "") if dialect_name else ""

    # 1. Dense vector ranking
    dense_ranked_rows: list[MemoryRow] = []
    if dialect == "postgresql":
        try:
            dense_stmt = (
                select(MemoryRow)
                .where(
                    MemoryRow.user_id == user_id,
                    MemoryRow.status == "active",
                    MemoryRow.embedding.is_not(None),
                )
                .order_by(MemoryRow.embedding.cosine_distance(query_vec))
                .limit(limit * 3)
            )
            dense_ranked_rows = list((await db.scalars(dense_stmt)).all())
        except Exception:
            dense_ranked_rows = []

    if not dense_ranked_rows:
        scored_dense: list[tuple[MemoryRow, float]] = []
        for r in rows:
            vec = r.embedding if r.embedding is not None else embed(r.content)
            try:
                scored_dense.append((r, cosine(query_vec, vec)))
            except Exception:
                continue
        if scored_dense:
            max_sim = max(s for _, s in scored_dense)
            min_thresh = max(0.45, max_sim - 0.15)
            filtered_dense = [(r, s) for r, s in scored_dense if s >= min_thresh]
            filtered_dense.sort(key=lambda pair: pair[1], reverse=True)
            dense_ranked_rows = [p[0] for p in filtered_dense[: limit * 3]]

    # 2. Sparse lexical / token overlap ranking
    query_terms = tokens(query)
    scored_sparse: list[tuple[MemoryRow, float]] = []
    now = datetime.now(UTC)
    for r in rows:
        terms = tokens(r.content)
        overlap = len(query_terms & terms)
        if overlap:
            created_at = r.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=UTC)
            else:
                created_at = created_at.astimezone(UTC)
            age_days = max(0, (now - created_at).days)
            score = (
                overlap / max(len(query_terms), 1) + min(r.confidence, 1) * 0.1 - age_days / 3650
            )
            scored_sparse.append((r, score))
    scored_sparse.sort(key=lambda pair: pair[1], reverse=True)
    sparse_ranked_rows = [p[0] for p in scored_sparse[: limit * 3]]

    # 3. Hybrid search combination using Reciprocal Rank Fusion
    fused = reciprocal_rank_fusion(
        [dense_ranked_rows, sparse_ranked_rows],
        k=60,
        key_fn=lambda r: r.id,
    )
    if fused:
        return [row for row, _ in fused[:limit]]
    return []


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
        embedding=embed(content),
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


def extract_implicit_facts(message: str) -> list[tuple[str, str]]:
    """Extract personal facts and preferences without requiring explicit 'remember' syntax."""
    if not message or len(message) > 4000:
        return []

    lowered = message.lower()
    if re.search(
        r"\b(?:api[ _-]?key|password|passphrase|secret|credential|access token|bearer token)\b|"
        r"sk-or-v1-[a-z0-9_-]+",
        lowered,
    ):
        return []

    facts = []
    sentences = re.split(r"(?<=[.!?\n])\s+", message.strip())
    for s in sentences:
        s_clean = s.strip(" \t-*\r\n")
        if not s_clean or len(s_clean) < 10 or len(s_clean) > 500:
            continue
        s_lower = s_clean.lower()
        if re.search(r"\b(?:api[ _-]?key|password|passphrase|secret|credential)\b", s_lower):
            continue

        if re.search(
            r"\b(?:i prefer|i like|i dislike|i avoid|i love|my favorite|"
            r"i always use|i never use|i want)\b",
            s_lower,
        ):
            facts.append(("preference", s_clean))
        elif re.search(
            r"\b(?:i am a|i am an|i work as|i work at|i live in|i moved to|my name is|"
            r"i study at)\b",
            s_lower,
        ):
            facts.append(("profile", s_clean))
        elif re.search(
            r"\b(?:i am building|i am working on|my project is|i'm developing|i'm creating)\b",
            s_lower,
        ):
            facts.append(("project", s_clean))
        elif re.search(
            r"\b(?:yesterday i|last week i|last year i|recently i decided|i learned that)\b",
            s_lower,
        ):
            facts.append(("episode", s_clean))

    return facts


async def process_reflection_job(
    db: AsyncSession, user_id: str, payload: dict
) -> list[str]:
    """Asynchronously reflect on a conversation exchange and extract/save personal facts."""
    conversation_id = payload.get("conversation_id")
    message = payload.get("message", "")
    if not message:
        return []

    policy = await policy_for(db, user_id)
    if not policy.enabled:
        return []

    facts = extract_implicit_facts(message)
    if not facts:
        return []

    auto_categories = set(json.loads(policy.auto_categories))
    approval_categories = set(json.loads(policy.approval_categories))
    never_auto = set(json.loads(policy.never_auto_categories))

    persisted_ids = []
    for category, fact in facts:
        if category in never_auto or category in SENSITIVE_CATEGORIES:
            if category in approval_categories:
                pending = await db.scalar(
                    select(MemoryCandidateRow).where(
                        MemoryCandidateRow.user_id == user_id,
                        MemoryCandidateRow.category == category,
                        MemoryCandidateRow.content == fact,
                        MemoryCandidateRow.status == "pending",
                    )
                )
                if not pending:
                    candidate = MemoryCandidateRow(
                        user_id=user_id,
                        content=fact,
                        category=category,
                        source_conversation_id=conversation_id,
                        confidence=0.8,
                    )
                    db.add(candidate)
                    await db.flush()
                    persisted_ids.append(candidate.id)
            continue

        if category in auto_categories:
            mem = await save_memory(
                db,
                user_id,
                fact,
                category,
                consent=True,
                source="agent-reflection",
                source_conversation_id=conversation_id,
            )
            persisted_ids.append(mem.id)
        elif category in approval_categories:
            pending = await db.scalar(
                select(MemoryCandidateRow).where(
                    MemoryCandidateRow.user_id == user_id,
                    MemoryCandidateRow.category == category,
                    MemoryCandidateRow.content == fact,
                    MemoryCandidateRow.status == "pending",
                )
            )
            if not pending:
                candidate = MemoryCandidateRow(
                    user_id=user_id,
                    content=fact,
                    category=category,
                    source_conversation_id=conversation_id,
                    confidence=0.75,
                )
                db.add(candidate)
                await db.flush()
                persisted_ids.append(candidate.id)

    return persisted_ids
