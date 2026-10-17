import hashlib
import json
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal, current_principal
from app.memory.service import policy_for, policy_json, save_memory
from app.persistence.models import (
    ApprovalRow,
    AuditRow,
    IdempotencyRow,
    JobRow,
    MemoryRow,
    NotificationRow,
    ProjectRow,
    ReminderRow,
    TaskRow,
)
from app.persistence.session import get_session

router = APIRouter(prefix="/api/v1")


def owned_or_404(row, label):
    if row is None:
        raise HTTPException(404, detail={"code": "not_found", "message": f"{label} not found"})
    return row


class MemoryInput(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    category: str = Field(default="preference", max_length=100)
    consent: bool
    source_conversation_id: str | None = None


class PolicyInput(BaseModel):
    enabled: bool = True
    auto_categories: list[str] = Field(default_factory=list, max_length=20)
    approval_categories: list[str] = Field(
        default_factory=lambda: ["profile", "preference", "project", "episode"], max_length=20
    )
    never_auto_categories: list[str] = Field(
        default_factory=lambda: ["health", "financial", "identity", "credential"], max_length=20
    )
    retention_days: int | None = Field(default=None, ge=1, le=3650)
    hosted_memory_allowed: bool = False


@router.get("/memory-policy")
async def get_memory_policy(
    principal: Principal = Depends(current_principal), db: AsyncSession = Depends(get_session)
):
    row = await policy_for(db, principal.user_id)
    await db.commit()
    return policy_json(row)


@router.put("/memory-policy")
async def set_memory_policy(
    payload: PolicyInput,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    row = await policy_for(db, principal.user_id)
    row.enabled = payload.enabled
    row.auto_categories = json.dumps(payload.auto_categories)
    row.approval_categories = json.dumps(payload.approval_categories)
    row.never_auto_categories = json.dumps(payload.never_auto_categories)
    row.retention_days = payload.retention_days
    row.hosted_memory_allowed = payload.hosted_memory_allowed
    await db.commit()
    return policy_json(row)


@router.post("/memories", status_code=201)
async def add_memory(
    payload: MemoryInput,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    try:
        row = await save_memory(
            db,
            principal.user_id,
            payload.content,
            payload.category,
            consent=payload.consent,
            source_conversation_id=payload.source_conversation_id,
        )
    except ValueError as exc:
        raise HTTPException(400, detail={"code": "memory_not_saved", "message": str(exc)}) from exc
    await db.commit()
    await db.refresh(row)
    return memory_view(row)


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
    }


@router.get("/memories")
async def memories(
    principal: Principal = Depends(current_principal), db: AsyncSession = Depends(get_session)
):
    rows = (
        await db.scalars(
            select(MemoryRow)
            .where(MemoryRow.user_id == principal.user_id)
            .order_by(MemoryRow.created_at.desc())
        )
    ).all()
    return {"items": [memory_view(row) for row in rows]}


@router.delete("/memories/{memory_id}", status_code=204)
async def forget_memory(
    memory_id: str,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    row = await db.scalar(
        select(MemoryRow).where(MemoryRow.id == memory_id, MemoryRow.user_id == principal.user_id)
    )
    await db.delete(owned_or_404(row, "Memory"))
    await db.commit()


@router.patch("/memories/{memory_id}")
async def edit_memory(
    memory_id: str,
    payload: MemoryInput,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    if not payload.consent:
        raise HTTPException(
            400, detail={"code": "consent_required", "message": "Explicit consent is required"}
        )
    row = owned_or_404(
        await db.scalar(
            select(MemoryRow).where(
                MemoryRow.id == memory_id, MemoryRow.user_id == principal.user_id
            )
        ),
        "Memory",
    )
    if row.content == payload.content.strip() and row.category == payload.category:
        row.source_conversation_id = payload.source_conversation_id or row.source_conversation_id
        row.updated_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(row)
        return memory_view(row)
    try:
        replacement = await save_memory(
            db,
            principal.user_id,
            payload.content,
            payload.category,
            consent=True,
            source_conversation_id=payload.source_conversation_id,
        )
    except ValueError as exc:
        raise HTTPException(400, detail={"code": "memory_not_saved", "message": str(exc)}) from exc
    row.status = "superseded"
    await db.commit()
    await db.refresh(replacement)
    return memory_view(replacement)


@router.get("/audit")
async def audit_events(
    principal: Principal = Depends(current_principal), db: AsyncSession = Depends(get_session)
):
    rows = (
        await db.scalars(
            select(AuditRow)
            .where(AuditRow.user_id == principal.user_id)
            .order_by(AuditRow.created_at.desc())
            .limit(100)
        )
    ).all()
    return {
        "items": [
            {
                "id": row.id,
                "action": row.action,
                "resource_id": row.resource_id,
                "outcome": row.outcome,
                "created_at": row.created_at,
            }
            for row in rows
        ]
    }


class ProjectInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    status: str = "active"
    priority: str = "normal"
    progress: str = ""
    blocker: str = ""
    next_action: str = ""
    target_at: datetime | None = None

    @field_validator("target_at")
    @classmethod
    def aware_target(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("target_at must include a timezone offset")
        return value


def project_view(row):
    return {
        k: getattr(row, k)
        for k in (
            "id",
            "title",
            "description",
            "status",
            "priority",
            "target_at",
            "progress",
            "blocker",
            "next_action",
            "created_at",
            "updated_at",
        )
    }


@router.post("/projects", status_code=201)
async def add_project(
    payload: ProjectInput,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    row = ProjectRow(user_id=principal.user_id, **payload.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return project_view(row)


@router.get("/projects")
async def projects(
    principal: Principal = Depends(current_principal), db: AsyncSession = Depends(get_session)
):
    rows = (
        await db.scalars(
            select(ProjectRow)
            .where(ProjectRow.user_id == principal.user_id)
            .order_by(ProjectRow.updated_at.desc())
        )
    ).all()
    return {"items": [project_view(row) for row in rows]}


@router.patch("/projects/{project_id}")
async def edit_project(
    project_id: str,
    payload: ProjectInput,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    row = owned_or_404(
        await db.scalar(
            select(ProjectRow).where(
                ProjectRow.id == project_id, ProjectRow.user_id == principal.user_id
            )
        ),
        "Project",
    )
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    await db.commit()
    await db.refresh(row)
    return project_view(row)


class TaskInput(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    project_id: str | None = None
    priority: str = "normal"
    due_at: datetime | None = None
    timezone: str = "UTC"

    @field_validator("timezone")
    @classmethod
    def valid_zone(cls, value):
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Unknown IANA timezone") from exc
        return value

    @field_validator("due_at")
    @classmethod
    def aware_due(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("due_at must include a timezone offset")
        return value


def task_view(row):
    return {
        k: getattr(row, k)
        for k in (
            "id",
            "title",
            "description",
            "project_id",
            "status",
            "priority",
            "due_at",
            "timezone",
            "completed_at",
            "created_at",
            "updated_at",
        )
    }


async def validate_project(db, user_id, project_id):
    if project_id and not await db.scalar(
        select(ProjectRow.id).where(ProjectRow.id == project_id, ProjectRow.user_id == user_id)
    ):
        raise HTTPException(
            404, detail={"code": "project_not_found", "message": "Project not found"}
        )


@router.post("/tasks", status_code=201)
async def add_task(
    payload: TaskInput,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    user = principal.user_id
    if idempotency_key:
        prior = await db.scalar(
            select(IdempotencyRow).where(
                IdempotencyRow.user_id == user, IdempotencyRow.key == idempotency_key
            )
        )
        if prior and prior.resource_type == "task":
            return task_view(await db.get(TaskRow, prior.resource_id))
        if prior:
            raise HTTPException(
                409,
                detail={
                    "code": "idempotency_key_reused",
                    "message": "Key was used for a different operation",
                },
            )
    await validate_project(db, user, payload.project_id)
    row = TaskRow(user_id=user, **payload.model_dump())
    db.add(row)
    await db.flush()
    if idempotency_key:
        db.add(
            IdempotencyRow(
                user_id=user, key=idempotency_key, resource_id=row.id, resource_type="task"
            )
        )
    db.add(AuditRow(user_id=user, action="task.create", resource_id=row.id, outcome="succeeded"))
    await db.commit()
    await db.refresh(row)
    return task_view(row)


@router.get("/tasks")
async def tasks(
    status: str | None = None,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    query = select(TaskRow).where(TaskRow.user_id == principal.user_id)
    if status:
        query = query.where(TaskRow.status == status)
    rows = (
        await db.scalars(
            query.order_by(TaskRow.due_at.asc().nullslast(), TaskRow.created_at.desc())
        )
    ).all()
    return {"items": [task_view(row) for row in rows]}


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    row = await db.scalar(
        select(TaskRow).where(TaskRow.id == task_id, TaskRow.user_id == principal.user_id)
    )
    return task_view(owned_or_404(row, "Task"))


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(
    task_id: str,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    row = await db.scalar(
        select(TaskRow).where(TaskRow.id == task_id, TaskRow.user_id == principal.user_id)
    )
    await db.delete(owned_or_404(row, "Task"))
    await db.commit()


@router.patch("/tasks/{task_id}")
async def edit_task(
    task_id: str,
    payload: TaskInput,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    row = owned_or_404(
        await db.scalar(
            select(TaskRow).where(TaskRow.id == task_id, TaskRow.user_id == principal.user_id)
        ),
        "Task",
    )
    await validate_project(db, principal.user_id, payload.project_id)
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    await db.commit()
    await db.refresh(row)
    return task_view(row)


@router.post("/tasks/{task_id}/complete")
async def complete_task(
    task_id: str,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    row = owned_or_404(
        await db.scalar(
            select(TaskRow).where(TaskRow.id == task_id, TaskRow.user_id == principal.user_id)
        ),
        "Task",
    )
    row.status = "completed"
    row.completed_at = datetime.now(UTC)
    db.add(
        AuditRow(
            user_id=principal.user_id,
            action="task.complete",
            resource_id=row.id,
            outcome="succeeded",
        )
    )
    await db.commit()
    await db.refresh(row)
    return task_view(row)


@router.post("/tasks/{task_id}/start")
async def start_task(
    task_id: str,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    row = owned_or_404(
        await db.scalar(
            select(TaskRow).where(TaskRow.id == task_id, TaskRow.user_id == principal.user_id)
        ),
        "Task",
    )
    if row.status in {"completed", "cancelled"}:
        raise HTTPException(
            409, detail={"code": "task_resolved", "message": "Task is already resolved"}
        )
    row.status = "in_progress"
    row.completed_at = None
    db.add(
        AuditRow(
            user_id=principal.user_id,
            action="task.start",
            resource_id=row.id,
            outcome="succeeded",
        )
    )
    await db.commit()
    await db.refresh(row)
    return task_view(row)


class ReminderInput(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    scheduled_at: datetime
    timezone: str = "UTC"
    task_id: str | None = None

    @field_validator("scheduled_at")
    @classmethod
    def aware_time(cls, value):
        if value.tzinfo is None:
            raise ValueError("scheduled_at must include a timezone offset")
        return value.astimezone(UTC)

    @field_validator("timezone")
    @classmethod
    def valid_zone(cls, value):
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Unknown IANA timezone") from exc
        return value


def reminder_view(row):
    return {
        k: getattr(row, k)
        for k in ("id", "text", "task_id", "scheduled_at", "timezone", "status", "created_at")
    }


@router.post("/reminders", status_code=201)
async def add_reminder(
    payload: ReminderInput,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    user = principal.user_id
    if payload.task_id and not await db.scalar(
        select(TaskRow.id).where(TaskRow.id == payload.task_id, TaskRow.user_id == user)
    ):
        raise HTTPException(404, detail={"code": "task_not_found", "message": "Task not found"})
    if idempotency_key:
        prior = await db.scalar(
            select(IdempotencyRow).where(
                IdempotencyRow.user_id == user, IdempotencyRow.key == idempotency_key
            )
        )
        if prior and prior.resource_type == "reminder":
            return reminder_view(await db.get(ReminderRow, prior.resource_id))
        if prior:
            raise HTTPException(
                409,
                detail={
                    "code": "idempotency_key_reused",
                    "message": "Key was used for a different operation",
                },
            )
    row = ReminderRow(
        user_id=user,
        text=payload.text,
        scheduled_at=payload.scheduled_at,
        timezone=payload.timezone,
        task_id=payload.task_id,
    )
    db.add(row)
    await db.flush()
    job = JobRow(
        user_id=user,
        reminder_id=row.id,
        scheduled_at=payload.scheduled_at,
        idempotency_key=f"reminder:{row.id}",
    )
    db.add(job)
    if idempotency_key:
        db.add(
            IdempotencyRow(
                user_id=user, key=idempotency_key, resource_id=row.id, resource_type="reminder"
            )
        )
    db.add(AuditRow(user_id=user, action="reminder.schedule", resource_id=row.id, outcome="queued"))
    await db.commit()
    await db.refresh(row)
    return reminder_view(row)


@router.get("/reminders")
async def reminders(
    principal: Principal = Depends(current_principal), db: AsyncSession = Depends(get_session)
):
    rows = (
        await db.scalars(
            select(ReminderRow)
            .where(ReminderRow.user_id == principal.user_id)
            .order_by(ReminderRow.scheduled_at)
        )
    ).all()
    return {"items": [reminder_view(row) for row in rows]}


@router.get("/reminders/{reminder_id}")
async def get_reminder(
    reminder_id: str,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    row = await db.scalar(
        select(ReminderRow).where(
            ReminderRow.id == reminder_id, ReminderRow.user_id == principal.user_id
        )
    )
    return reminder_view(owned_or_404(row, "Reminder"))


@router.delete("/reminders/{reminder_id}")
async def cancel_reminder(
    reminder_id: str,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    row = owned_or_404(
        await db.scalar(
            select(ReminderRow).where(
                ReminderRow.id == reminder_id, ReminderRow.user_id == principal.user_id
            )
        ),
        "Reminder",
    )
    row.status = "cancelled"
    job = await db.scalar(
        select(JobRow).where(JobRow.reminder_id == row.id, JobRow.status == "queued")
    )
    if job:
        job.status = "cancelled"
    await db.commit()
    return reminder_view(row)


@router.get("/notifications")
async def notifications(
    principal: Principal = Depends(current_principal), db: AsyncSession = Depends(get_session)
):
    rows = (
        await db.scalars(
            select(NotificationRow)
            .where(NotificationRow.user_id == principal.user_id)
            .order_by(NotificationRow.created_at.desc())
            .limit(100)
        )
    ).all()
    return {
        "items": [
            {
                "id": r.id,
                "text": r.text,
                "job_id": r.job_id,
                "created_at": r.created_at,
                "read_at": r.read_at,
            }
            for r in rows
        ]
    }


@router.get("/jobs")
async def jobs(
    principal: Principal = Depends(current_principal), db: AsyncSession = Depends(get_session)
):
    rows = (
        await db.scalars(
            select(JobRow)
            .where(JobRow.user_id == principal.user_id)
            .order_by(JobRow.created_at.desc())
            .limit(100)
        )
    ).all()
    return {"items": [job_view(row) for row in rows]}


def job_view(row):
    return {
        k: getattr(row, k)
        for k in (
            "id",
            "job_type",
            "reminder_id",
            "scheduled_at",
            "status",
            "attempts",
            "last_error",
            "created_at",
            "started_at",
            "completed_at",
        )
    }


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: str,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    return job_view(
        owned_or_404(
            await db.scalar(
                select(JobRow).where(JobRow.id == job_id, JobRow.user_id == principal.user_id)
            ),
            "Job",
        )
    )


class ActionProposal(BaseModel):
    action: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    arguments: dict = Field(default_factory=dict)


@router.post("/approvals", status_code=201)
async def propose_action(
    payload: ActionProposal,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    safe_arguments = redact_action_arguments(payload.arguments)
    serialized = json.dumps(safe_arguments, sort_keys=True, separators=(",", ":"))
    row = ApprovalRow(
        user_id=principal.user_id,
        action=payload.action,
        description=payload.description,
        arguments=serialized,
        payload_hash=hashlib.sha256(serialized.encode()).hexdigest(),
    )
    db.add(row)
    await db.flush()
    db.add(
        AuditRow(
            user_id=principal.user_id,
            action="approval.proposed",
            resource_id=row.id,
            outcome="pending",
        )
    )
    await db.commit()
    await db.refresh(row)
    return approval_view(row)


def approval_view(row):
    return {
        "id": row.id,
        "action": row.action,
        "description": row.description,
        "status": row.status,
        "created_at": row.created_at,
        "decided_at": row.decided_at,
    }


def redact_action_arguments(value):
    sensitive = {"token", "secret", "password", "credential", "authorization", "api_key"}
    if isinstance(value, dict):
        return {
            key: "[redacted]" if key.lower() in sensitive else redact_action_arguments(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_action_arguments(item) for item in value]
    return value


@router.get("/approvals")
async def approvals(
    principal: Principal = Depends(current_principal), db: AsyncSession = Depends(get_session)
):
    rows = (
        await db.scalars(
            select(ApprovalRow)
            .where(ApprovalRow.user_id == principal.user_id)
            .order_by(ApprovalRow.created_at.desc())
        )
    ).all()
    return {"items": [approval_view(row) for row in rows]}


@router.post("/approvals/{approval_id}/{decision}")
async def decide_approval(
    approval_id: str,
    decision: str,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    if decision not in {"approve", "reject"}:
        raise HTTPException(
            400, detail={"code": "invalid_decision", "message": "Use approve or reject"}
        )
    row = owned_or_404(
        await db.scalar(
            select(ApprovalRow).where(
                ApprovalRow.id == approval_id, ApprovalRow.user_id == principal.user_id
            )
        ),
        "Approval",
    )
    if row.status != "pending":
        raise HTTPException(
            409, detail={"code": "approval_resolved", "message": "Approval is no longer pending"}
        )
    payload_hash = hashlib.sha256(row.arguments.encode()).hexdigest()
    if payload_hash != row.payload_hash:
        raise HTTPException(
            409, detail={"code": "payload_changed", "message": "Approved action payload changed"}
        )
    row.status = "approved" if decision == "approve" else "rejected"
    row.decided_at = datetime.now(UTC)
    db.add(
        AuditRow(
            user_id=principal.user_id,
            action=f"approval.{decision}",
            resource_id=row.id,
            outcome=row.status,
        )
    )
    await db.commit()
    await db.refresh(row)
    return approval_view(row)
