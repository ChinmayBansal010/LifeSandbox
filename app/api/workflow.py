import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal, current_principal
from app.persistence.models import (
    ApprovalRow,
    AuditRow,
    IdempotencyRow,
    JobRow,
    ProjectRow,
    ReminderRow,
    TaskRow,
)
from app.persistence.session import get_session

router = APIRouter(prefix="/api/v1")


class TaskAction(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    project_id: str | None = None
    priority: Literal["low", "normal", "high"] = "normal"
    due_at: datetime | None = None
    timezone: str = "UTC"

    @field_validator("due_at")
    @classmethod
    def aware_due(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("due_at must include a timezone offset")
        return value

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Unknown IANA timezone") from exc
        return value


class ReminderSchedule(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    scheduled_at: datetime
    timezone: str = "UTC"
    task_id: str | None = None
    recurrence: Literal["none", "daily", "weekly"] = "none"
    channel: Literal["in_app"] = "in_app"

    @field_validator("scheduled_at")
    @classmethod
    def aware_scheduled_at(cls, value):
        if value.tzinfo is None:
            raise ValueError("scheduled_at must include a timezone offset")
        return value.astimezone(UTC)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Unknown IANA timezone") from exc
        return value


class ReminderEdit(ReminderSchedule):
    pass


def task_view(row: TaskRow):
    return {
        key: getattr(row, key)
        for key in (
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


def reminder_view(row: ReminderRow):
    return {
        key: getattr(row, key)
        for key in (
            "id",
            "text",
            "task_id",
            "scheduled_at",
            "timezone",
            "recurrence",
            "channel",
            "status",
            "created_at",
        )
    }


async def validate_project(db: AsyncSession, user_id: str, project_id: str | None):
    if project_id and not await db.scalar(
        select(ProjectRow.id).where(ProjectRow.id == project_id, ProjectRow.user_id == user_id)
    ):
        raise HTTPException(404, detail={"code": "not_found", "message": "Project not found"})


async def validate_task(db: AsyncSession, user_id: str, task_id: str | None):
    if task_id and not await db.scalar(
        select(TaskRow.id).where(TaskRow.id == task_id, TaskRow.user_id == user_id)
    ):
        raise HTTPException(404, detail={"code": "not_found", "message": "Task not found"})


def request_hash(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


async def existing_idempotent_resource(db: AsyncSession, user_id: str, key: str, digest: str):
    prior = await db.scalar(
        select(IdempotencyRow).where(IdempotencyRow.user_id == user_id, IdempotencyRow.key == key)
    )
    if prior is None:
        return None
    if prior.request_hash and prior.request_hash != digest:
        raise HTTPException(
            409,
            detail={
                "code": "idempotency_key_reused",
                "message": "Key was used with different input",
            },
        )
    if prior.resource_type == "reminder":
        row = await db.get(ReminderRow, prior.resource_id)
        if row is None:
            raise HTTPException(404, detail={"code": "not_found", "message": "Reminder not found"})
        return reminder_view(row)
    if prior.resource_type == "task":
        row = await db.get(TaskRow, prior.resource_id)
        if row is None:
            raise HTTPException(404, detail={"code": "not_found", "message": "Task not found"})
        return task_view(row)
    raise HTTPException(
        409,
        detail={"code": "idempotency_key_reused", "message": "Key was used for another operation"},
    )


@router.post("/reminders/recurring", status_code=201)
async def create_recurring_reminder(
    payload: ReminderSchedule,
    request: Request,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    if payload.recurrence == "none":
        raise HTTPException(
            422,
            detail={"code": "recurrence_required", "message": "Choose daily or weekly recurrence"},
        )
    await validate_task(db, principal.user_id, payload.task_id)
    key = request.headers.get("Idempotency-Key")
    digest = request_hash(payload.model_dump(mode="json"))
    if key:
        existing = await existing_idempotent_resource(db, principal.user_id, key, digest)
        if existing:
            return existing
    reminder = ReminderRow(user_id=principal.user_id, **payload.model_dump())
    db.add(reminder)
    await db.flush()
    db.add(
        JobRow(
            user_id=principal.user_id,
            reminder_id=reminder.id,
            scheduled_at=reminder.scheduled_at,
            idempotency_key=f"reminder:{reminder.id}:{reminder.scheduled_at.isoformat()}",
        )
    )
    if key:
        db.add(
            IdempotencyRow(
                user_id=principal.user_id,
                key=key,
                resource_id=reminder.id,
                resource_type="reminder",
                request_hash=digest,
            )
        )
    db.add(
        AuditRow(
            user_id=principal.user_id,
            action="reminder.schedule",
            resource_id=reminder.id,
            outcome="queued",
        )
    )
    await db.commit()
    await db.refresh(reminder)
    return reminder_view(reminder)


@router.patch("/reminders/{reminder_id}")
async def edit_reminder(
    reminder_id: str,
    payload: ReminderEdit,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    reminder = await db.scalar(
        select(ReminderRow).where(
            ReminderRow.id == reminder_id,
            ReminderRow.user_id == principal.user_id,
            ReminderRow.status == "pending",
        )
    )
    if reminder is None:
        raise HTTPException(
            404, detail={"code": "not_found", "message": "Pending reminder not found"}
        )
    await validate_task(db, principal.user_id, payload.task_id)
    for key, value in payload.model_dump().items():
        setattr(reminder, key, value)
    job = await db.scalar(
        select(JobRow).where(JobRow.reminder_id == reminder.id, JobRow.status == "queued")
    )
    if job:
        job.scheduled_at = reminder.scheduled_at
        job.idempotency_key = f"reminder:{reminder.id}:edit:{uuid4()}"
    db.add(
        AuditRow(
            user_id=principal.user_id,
            action="reminder.update",
            resource_id=reminder.id,
            outcome="succeeded",
        )
    )
    await db.commit()
    await db.refresh(reminder)
    return reminder_view(reminder)


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    task = await db.scalar(
        select(TaskRow).where(TaskRow.id == task_id, TaskRow.user_id == principal.user_id)
    )
    if task is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Task not found"})
    if task.status in {"completed", "cancelled"}:
        raise HTTPException(
            409, detail={"code": "task_resolved", "message": "Task is already resolved"}
        )
    task.status = "cancelled"
    task.completed_at = datetime.now(UTC)
    db.add(
        AuditRow(
            user_id=principal.user_id,
            action="task.cancel",
            resource_id=task.id,
            outcome="succeeded",
        )
    )
    await db.commit()
    await db.refresh(task)
    return task_view(task)


@router.get("/reminder-schedules")
async def list_reminder_schedules(
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    rows = (
        await db.scalars(
            select(ReminderRow)
            .where(ReminderRow.user_id == principal.user_id)
            .order_by(ReminderRow.scheduled_at)
        )
    ).all()
    return {"items": [reminder_view(row) for row in rows]}


@router.post("/approved-actions/{approval_id}/execute")
async def execute_approved_action(
    approval_id: str,
    request: Request,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    approval = await db.scalar(
        select(ApprovalRow).where(
            ApprovalRow.id == approval_id, ApprovalRow.user_id == principal.user_id
        )
    )
    if approval is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Approval not found"})
    serialized = approval.arguments
    digest = hashlib.sha256(serialized.encode()).hexdigest()
    if digest != approval.payload_hash:
        raise HTTPException(
            409, detail={"code": "payload_changed", "message": "Approved action payload changed"}
        )
    if approval.status == "executed" and approval.result_resource_id:
        return {
            "status": approval.status,
            "resource_type": approval.result_resource_type,
            "resource_id": approval.result_resource_id,
        }
    if approval.status != "approved":
        raise HTTPException(
            409,
            detail={
                "code": "approval_required",
                "message": "Approve this action before executing it",
            },
        )
    expires_at = approval.expires_at or approval.created_at + timedelta(hours=24)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if datetime.now(UTC) >= expires_at:
        approval.status = "expired"
        approval.decided_at = datetime.now(UTC)
        db.add(
            AuditRow(
                user_id=principal.user_id,
                action="approval.expire",
                resource_id=approval.id,
                outcome="expired",
                correlation_id=request.state.request_id,
            )
        )
        await db.commit()
        raise HTTPException(
            409, detail={"code": "approval_expired", "message": "Approval has expired"}
        )
    if approval.action not in {"task.create", "reminder.create"}:
        raise HTTPException(
            422,
            detail={
                "code": "unsupported_action",
                "message": "This action has no safe local executor",
            },
        )
    try:
        arguments = json.loads(serialized)
        action_payload = (
            TaskAction.model_validate(arguments)
            if approval.action == "task.create"
            else ReminderSchedule.model_validate(arguments)
        )
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(
            422, detail={"code": "invalid_action", "message": "Approved arguments are invalid"}
        ) from exc

    key = f"approval:{approval.id}"
    existing = await db.scalar(
        select(IdempotencyRow).where(
            IdempotencyRow.user_id == principal.user_id, IdempotencyRow.key == key
        )
    )
    if existing:
        if existing.request_hash and existing.request_hash != digest:
            raise HTTPException(
                409,
                detail={"code": "payload_changed", "message": "Idempotent action payload changed"},
            )
        approval.status = "executed"
        approval.result_resource_type = existing.resource_type
        approval.result_resource_id = existing.resource_id
        await db.commit()
        return {
            "status": "executed",
            "resource_type": existing.resource_type,
            "resource_id": existing.resource_id,
        }

    claim = await db.execute(
        update(ApprovalRow)
        .where(
            ApprovalRow.id == approval.id,
            ApprovalRow.user_id == principal.user_id,
            ApprovalRow.status == "approved",
        )
        .values(status="executing")
        .returning(ApprovalRow.id)
    )
    if claim.scalar_one_or_none() is None:
        raise HTTPException(
            409,
            detail={"code": "approval_in_progress", "message": "Action is already being processed"},
        )

    if approval.action == "task.create":
        task_data = action_payload.model_dump()
        await validate_project(db, principal.user_id, task_data["project_id"])
        task = TaskRow(user_id=principal.user_id, **task_data)
        db.add(task)
        await db.flush()
        resource_id = task.id
        resource_type = "task"
    else:
        reminder_data = action_payload.model_dump()
        await validate_task(db, principal.user_id, reminder_data["task_id"])
        reminder = ReminderRow(user_id=principal.user_id, **reminder_data)
        db.add(reminder)
        await db.flush()
        db.add(
            JobRow(
                user_id=principal.user_id,
                reminder_id=reminder.id,
                scheduled_at=reminder.scheduled_at,
                idempotency_key=f"reminder:{reminder.id}:{reminder.scheduled_at.isoformat()}",
            )
        )
        resource_id = reminder.id
        resource_type = "reminder"
    db.add(
        IdempotencyRow(
            user_id=principal.user_id,
            key=key,
            resource_id=resource_id,
            resource_type=resource_type,
            request_hash=digest,
        )
    )
    approval.status = "executed"
    approval.result_resource_type = resource_type
    approval.result_resource_id = resource_id
    approval.correlation_id = request.state.request_id
    approval.decided_at = datetime.now(UTC)
    db.add(
        AuditRow(
            user_id=principal.user_id,
            action=f"approval.execute.{approval.action}",
            resource_id=approval.id,
            outcome="succeeded",
            correlation_id=request.state.request_id,
        )
    )
    await db.commit()
    return {"status": "executed", "resource_type": resource_type, "resource_id": resource_id}
