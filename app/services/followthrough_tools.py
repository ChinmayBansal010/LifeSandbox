import hashlib
import json
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models import (
    AuditRow,
    IdempotencyRow,
    JobRow,
    ProjectRow,
    ReminderRow,
    TaskRow,
)


class TaskWrite(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    project_id: str | None = None
    priority: Literal["low", "normal", "high"] = "normal"
    due_at: datetime | None = None
    timezone: str = "UTC"

    @field_validator("due_at")
    @classmethod
    def due_time_is_aware(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("due_at must include a timezone offset")
        return value.astimezone(UTC) if value else None

    @field_validator("timezone")
    @classmethod
    def timezone_exists(cls, value):
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Unknown IANA timezone") from exc
        return value


class ReminderWrite(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    scheduled_at: datetime
    timezone: str
    task_id: str | None = None
    recurrence: Literal["none", "daily", "weekly"] = "none"

    @field_validator("scheduled_at")
    @classmethod
    def schedule_is_aware(cls, value):
        if value.tzinfo is None:
            raise ValueError("scheduled_at must include a timezone offset")
        return value.astimezone(UTC)

    @field_validator("timezone")
    @classmethod
    def timezone_exists(cls, value):
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Unknown IANA timezone") from exc
        return value


class TaskChanges(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    project_id: str | None = None
    priority: Literal["low", "normal", "high"] | None = None
    due_at: datetime | None = None
    timezone: str | None = None

    @field_validator("due_at")
    @classmethod
    def due_time_is_aware(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("due_at must include a timezone offset")
        return value.astimezone(UTC) if value else None

    @field_validator("timezone")
    @classmethod
    def timezone_exists(cls, value):
        if value is not None:
            try:
                ZoneInfo(value)
            except ZoneInfoNotFoundError as exc:
                raise ValueError("Unknown IANA timezone") from exc
        return value


class ReminderChanges(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=500)
    scheduled_at: datetime | None = None
    timezone: str | None = None
    recurrence: Literal["none", "daily", "weekly"] | None = None

    @field_validator("scheduled_at")
    @classmethod
    def schedule_is_aware(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("scheduled_at must include a timezone offset")
        return value.astimezone(UTC) if value else None

    @field_validator("timezone")
    @classmethod
    def timezone_exists(cls, value):
        if value is not None:
            try:
                ZoneInfo(value)
            except ZoneInfoNotFoundError as exc:
                raise ValueError("Unknown IANA timezone") from exc
        return value


def task_view(row: TaskRow):
    return {
        "id": row.id,
        "title": row.title,
        "description": row.description,
        "project_id": row.project_id,
        "status": row.status,
        "priority": row.priority,
        "due_at": row.due_at.isoformat() if row.due_at else None,
        "timezone": row.timezone,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def reminder_view(row: ReminderRow):
    return {
        "id": row.id,
        "text": row.text,
        "task_id": row.task_id,
        "scheduled_at": row.scheduled_at.isoformat(),
        "timezone": row.timezone,
        "recurrence": row.recurrence,
        "channel": row.channel,
        "status": row.status,
    }


async def execute_followthrough_tool(
    db: AsyncSession,
    user_id: str,
    conversation_id: str,
    call_id: str,
    name: str,
    arguments: dict,
):
    if name == "list_tasks":
        query = select(TaskRow).where(TaskRow.user_id == user_id)
        if arguments.get("status"):
            query = query.where(TaskRow.status == arguments["status"])
        rows = (await db.scalars(query.order_by(TaskRow.due_at.asc().nullslast()).limit(50))).all()
        return {"items": [task_view(row) for row in rows]}

    if name == "create_task":
        payload = TaskWrite.model_validate(arguments)
        if payload.project_id and not await db.scalar(
            select(ProjectRow.id).where(
                ProjectRow.id == payload.project_id, ProjectRow.user_id == user_id
            )
        ):
            raise ValueError("Project not found")
        data = payload.model_dump(mode="json")
        digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
        key = f"chat:{conversation_id}:{call_id}" if call_id else None
        existing = await _existing_task(db, user_id, key, digest)
        if existing:
            return task_view(existing)
        row = TaskRow(user_id=user_id, **payload.model_dump())
        db.add(row)
        await db.flush()
        await _save_idempotency(db, user_id, key, row.id, "task", digest)
        db.add(
            AuditRow(user_id=user_id, action="task.create", resource_id=row.id, outcome="succeeded")
        )
        return task_view(row)

    if name in {"update_task", "complete_task", "cancel_task"}:
        task = await db.scalar(
            select(TaskRow).where(
                TaskRow.id == arguments.get("task_id"), TaskRow.user_id == user_id
            )
        )
        if task is None:
            raise ValueError("Task not found")
        if name == "update_task":
            changes = TaskChanges.model_validate(arguments)
            values = changes.model_dump(exclude_unset=True)
            if (
                "project_id" in values
                and values["project_id"]
                and not await db.scalar(
                    select(ProjectRow.id).where(
                        ProjectRow.id == values["project_id"], ProjectRow.user_id == user_id
                    )
                )
            ):
                raise ValueError("Project not found")
            for key, value in values.items():
                setattr(task, key, value)
            db.add(
                AuditRow(
                    user_id=user_id, action="task.update", resource_id=task.id, outcome="succeeded"
                )
            )
        else:
            if task.status in {"completed", "cancelled"}:
                raise ValueError("Task is already resolved")
            task.status = "completed" if name == "complete_task" else "cancelled"
            task.completed_at = datetime.now(UTC)
            db.add(
                AuditRow(
                    user_id=user_id,
                    action=f"task.{task.status}",
                    resource_id=task.id,
                    outcome="succeeded",
                )
            )
        await db.flush()
        return task_view(task)

    if name == "list_reminders":
        rows = (
            await db.scalars(
                select(ReminderRow)
                .where(ReminderRow.user_id == user_id)
                .order_by(ReminderRow.scheduled_at)
                .limit(50)
            )
        ).all()
        return {"items": [reminder_view(row) for row in rows]}

    if name == "create_reminder":
        payload = ReminderWrite.model_validate(arguments)
        if payload.task_id and not await db.scalar(
            select(TaskRow.id).where(TaskRow.id == payload.task_id, TaskRow.user_id == user_id)
        ):
            raise ValueError("Task not found")
        data = payload.model_dump(mode="json")
        digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
        key = f"chat:{conversation_id}:{call_id}" if call_id else None
        existing = await _existing_reminder(db, user_id, key, digest)
        if existing:
            return reminder_view(existing)
        row = ReminderRow(user_id=user_id, **payload.model_dump(), channel="in_app")
        db.add(row)
        await db.flush()
        db.add(
            JobRow(
                user_id=user_id,
                reminder_id=row.id,
                scheduled_at=row.scheduled_at,
                idempotency_key=f"reminder:{row.id}:{row.scheduled_at.isoformat()}",
            )
        )
        await _save_idempotency(db, user_id, key, row.id, "reminder", digest)
        db.add(
            AuditRow(
                user_id=user_id, action="reminder.schedule", resource_id=row.id, outcome="queued"
            )
        )
        return reminder_view(row)

    if name in {"update_reminder", "cancel_reminder"}:
        reminder = await db.scalar(
            select(ReminderRow).where(
                ReminderRow.id == arguments.get("reminder_id"),
                ReminderRow.user_id == user_id,
                ReminderRow.status == "pending",
            )
        )
        if reminder is None:
            raise ValueError("Pending reminder not found")
        if name == "cancel_reminder":
            reminder.status = "cancelled"
            job = await db.scalar(
                select(JobRow).where(JobRow.reminder_id == reminder.id, JobRow.status == "queued")
            )
            if job:
                job.status = "cancelled"
            action = "reminder.cancel"
        else:
            changes = ReminderChanges.model_validate(arguments).model_dump(exclude_unset=True)
            for key, value in changes.items():
                if value is not None:
                    setattr(reminder, key, value)
            job = await db.scalar(
                select(JobRow).where(JobRow.reminder_id == reminder.id, JobRow.status == "queued")
            )
            if job:
                job.scheduled_at = reminder.scheduled_at
                job.idempotency_key = f"reminder:{reminder.id}:edit:{uuid4()}"
            action = "reminder.update"
        db.add(
            AuditRow(user_id=user_id, action=action, resource_id=reminder.id, outcome="succeeded")
        )
        await db.flush()
        return reminder_view(reminder)

    raise ValueError("Unsupported follow-through operation")


async def _existing_task(db, user_id: str, key: str | None, digest: str):
    if key is None:
        return None
    prior = await db.scalar(
        select(IdempotencyRow).where(IdempotencyRow.user_id == user_id, IdempotencyRow.key == key)
    )
    if prior is None:
        return None
    if prior.request_hash and prior.request_hash != digest:
        raise ValueError("Idempotency key reused with different task details")
    if prior.resource_type != "task":
        raise ValueError("Idempotency key reused for another operation")
    row = await db.get(TaskRow, prior.resource_id)
    if row is None:
        raise ValueError("Idempotent task no longer exists")
    return row


async def _existing_reminder(db, user_id: str, key: str | None, digest: str):
    if key is None:
        return None
    prior = await db.scalar(
        select(IdempotencyRow).where(IdempotencyRow.user_id == user_id, IdempotencyRow.key == key)
    )
    if prior is None:
        return None
    if prior.request_hash and prior.request_hash != digest:
        raise ValueError("Idempotency key reused with different reminder details")
    if prior.resource_type != "reminder":
        raise ValueError("Idempotency key reused for another operation")
    row = await db.get(ReminderRow, prior.resource_id)
    if row is None:
        raise ValueError("Idempotent reminder no longer exists")
    return row


async def _save_idempotency(
    db, user_id: str, key, resource_id: str, resource_type: str, digest: str
):
    if key:
        db.add(
            IdempotencyRow(
                user_id=user_id,
                key=key,
                resource_id=resource_id,
                resource_type=resource_type,
                request_hash=digest,
            )
        )
