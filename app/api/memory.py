from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal, current_principal
from app.memory.service import policy_for, save_memory, search_memories
from app.persistence.models import (
    AuditRow,
    MemoryCandidateRow,
    MemoryRow,
    ProjectRow,
)
from app.persistence.session import get_session

router = APIRouter(prefix="/api/v1")


def memory_view(row: MemoryRow):
    return {
        "id": row.id,
        "content": row.content,
        "category": row.category,
        "source": row.source,
        "status": row.status,
        "confidence": row.confidence,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "source_conversation_id": row.source_conversation_id,
        "project_id": row.project_id,
    }


def candidate_view(row: MemoryCandidateRow):
    return {
        "id": row.id,
        "content": row.content,
        "category": row.category,
        "source_conversation_id": row.source_conversation_id,
        "status": row.status,
        "confidence": row.confidence,
        "memory_id": row.memory_id,
        "created_at": row.created_at,
        "resolved_at": row.resolved_at,
    }


@router.get("/memories/search")
async def find_memories(
    query: str,
    limit: int = 5,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    if not query.strip() or not 1 <= limit <= 20:
        raise HTTPException(
            422, detail={"code": "invalid_search", "message": "Invalid query or limit"}
        )
    rows = await search_memories(db, principal.user_id, query, limit)
    await db.commit()
    return {"items": [memory_view(row) for row in rows]}


@router.get("/memories/{memory_id}")
async def get_memory(
    memory_id: str,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    row = await db.scalar(
        select(MemoryRow).where(MemoryRow.id == memory_id, MemoryRow.user_id == principal.user_id)
    )
    if row is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Memory not found"})
    return memory_view(row)


@router.post("/memories/{memory_id}/archive")
async def archive_memory(
    memory_id: str,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    row = await db.scalar(
        select(MemoryRow).where(MemoryRow.id == memory_id, MemoryRow.user_id == principal.user_id)
    )
    if row is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Memory not found"})
    row.status = "archived"
    db.add(
        AuditRow(
            user_id=principal.user_id,
            action="memory.archive",
            resource_id=row.id,
            outcome="succeeded",
        )
    )
    await db.commit()
    await db.refresh(row)
    return memory_view(row)


class ProjectLink(BaseModel):
    project_id: str | None


@router.patch("/memories/{memory_id}/project")
async def link_memory_project(
    memory_id: str,
    payload: ProjectLink,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    row = await db.scalar(
        select(MemoryRow).where(MemoryRow.id == memory_id, MemoryRow.user_id == principal.user_id)
    )
    if row is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Memory not found"})
    if payload.project_id and not await db.scalar(
        select(ProjectRow.id).where(
            ProjectRow.id == payload.project_id, ProjectRow.user_id == principal.user_id
        )
    ):
        raise HTTPException(404, detail={"code": "not_found", "message": "Project not found"})
    row.project_id = payload.project_id
    await db.commit()
    await db.refresh(row)
    return memory_view(row)


@router.get("/memory-candidates")
async def list_memory_candidates(
    status: str = "pending",
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    if status not in {"pending", "approved", "rejected"}:
        raise HTTPException(422, detail={"code": "invalid_status", "message": "Unknown status"})
    rows = (
        await db.scalars(
            select(MemoryCandidateRow)
            .where(
                MemoryCandidateRow.user_id == principal.user_id, MemoryCandidateRow.status == status
            )
            .order_by(MemoryCandidateRow.created_at.desc())
        )
    ).all()
    return {"items": [candidate_view(row) for row in rows]}


@router.post("/memory-candidates/{candidate_id}/approve")
async def approve_memory_candidate(
    candidate_id: str,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    row = await db.scalar(
        select(MemoryCandidateRow).where(
            MemoryCandidateRow.id == candidate_id,
            MemoryCandidateRow.user_id == principal.user_id,
        )
    )
    if row is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Candidate not found"})
    if row.status != "pending":
        raise HTTPException(
            409, detail={"code": "candidate_resolved", "message": "Candidate is no longer pending"}
        )
    policy = await policy_for(db, principal.user_id)
    if not policy.enabled:
        raise HTTPException(
            409, detail={"code": "memory_disabled", "message": "Local memory is disabled"}
        )
    try:
        memory = await save_memory(
            db,
            principal.user_id,
            row.content,
            row.category,
            consent=True,
            source="chat-candidate-approved",
            source_conversation_id=row.source_conversation_id,
        )
    except ValueError as exc:
        raise HTTPException(400, detail={"code": "memory_not_saved", "message": str(exc)}) from exc
    row.status = "approved"
    row.memory_id = memory.id
    row.resolved_at = datetime.now(UTC)
    db.add(
        AuditRow(
            user_id=principal.user_id,
            action="memory_candidate.approve",
            resource_id=row.id,
            outcome="succeeded",
        )
    )
    await db.commit()
    await db.refresh(memory)
    return {"candidate": candidate_view(row), "memory": memory_view(memory)}


@router.post("/memory-candidates/{candidate_id}/reject")
async def reject_memory_candidate(
    candidate_id: str,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    row = await db.scalar(
        select(MemoryCandidateRow).where(
            MemoryCandidateRow.id == candidate_id,
            MemoryCandidateRow.user_id == principal.user_id,
        )
    )
    if row is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Candidate not found"})
    if row.status != "pending":
        raise HTTPException(
            409, detail={"code": "candidate_resolved", "message": "Candidate is no longer pending"}
        )
    row.status = "rejected"
    row.resolved_at = datetime.now(UTC)
    db.add(
        AuditRow(
            user_id=principal.user_id,
            action="memory_candidate.reject",
            resource_id=row.id,
            outcome="succeeded",
        )
    )
    await db.commit()
    await db.refresh(row)
    return candidate_view(row)
