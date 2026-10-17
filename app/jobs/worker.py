import asyncio
import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select, update

from app.persistence.models import JobRow, NotificationRow, ReminderRow
from app.persistence.session import SessionLocal

logger = logging.getLogger("life_sandbox.jobs")
MAX_ATTEMPTS = 3
LEASE_SECONDS = 300


def next_occurrence(scheduled_at: datetime, timezone: str, recurrence: str) -> datetime:
    local_time = scheduled_at.astimezone(ZoneInfo(timezone))
    increment = timedelta(days=1 if recurrence == "daily" else 7)
    return (local_time + increment).astimezone(UTC)


async def run_due_once(now: datetime | None = None, limit: int = 25) -> int:
    """Claim due reminders, recover expired worker leases, and persist delivery once."""
    now = now or datetime.now(UTC)
    stale_before = now - timedelta(seconds=LEASE_SECONDS)
    processed = 0
    async with SessionLocal() as db:
        exhausted_reminders = set(
            (
                await db.scalars(
                    select(JobRow.reminder_id).where(
                        JobRow.job_type == "reminder_delivery",
                        JobRow.status == "running",
                        JobRow.started_at <= stale_before,
                        JobRow.attempts >= MAX_ATTEMPTS,
                        JobRow.reminder_id.is_not(None),
                    )
                )
            ).all()
        )
        await db.execute(
            update(JobRow)
            .where(
                JobRow.job_type == "reminder_delivery",
                JobRow.status == "running",
                JobRow.started_at <= stale_before,
                JobRow.attempts >= MAX_ATTEMPTS,
            )
            .values(status="failed", completed_at=now, last_error="worker_lease_expired")
        )
        if exhausted_reminders:
            await db.execute(
                update(ReminderRow)
                .where(ReminderRow.id.in_(exhausted_reminders), ReminderRow.status == "pending")
                .values(status="failed")
            )
        await db.commit()
        ids = list(
            (
                await db.scalars(
                    select(JobRow.id)
                    .where(
                        JobRow.job_type == "reminder_delivery",
                        or_(
                            and_(JobRow.status == "queued", JobRow.scheduled_at <= now),
                            and_(JobRow.status == "running", JobRow.started_at <= stale_before),
                        ),
                        JobRow.attempts < MAX_ATTEMPTS,
                    )
                    .order_by(JobRow.scheduled_at)
                    .limit(limit)
                )
            ).all()
        )
    for job_id in ids:
        async with SessionLocal() as db:
            claim = await db.execute(
                update(JobRow)
                .where(
                    JobRow.id == job_id,
                    JobRow.attempts < MAX_ATTEMPTS,
                    or_(
                        and_(JobRow.status == "queued", JobRow.scheduled_at <= now),
                        and_(JobRow.status == "running", JobRow.started_at <= stale_before),
                    ),
                )
                .values(status="running", started_at=now, attempts=JobRow.attempts + 1)
                .returning(JobRow.id)
            )
            if claim.scalar_one_or_none() is None:
                continue
            job = await db.get(JobRow, job_id)
            if job is None:
                await db.rollback()
                continue
            try:
                reminder = await db.get(ReminderRow, job.reminder_id) if job.reminder_id else None
                if reminder is None or reminder.status != "pending":
                    job.status = "cancelled"
                else:
                    existing = await db.scalar(
                        select(NotificationRow.id).where(NotificationRow.job_id == job.id)
                    )
                    if not existing:
                        db.add(
                            NotificationRow(user_id=job.user_id, job_id=job.id, text=reminder.text)
                        )
                    if reminder.recurrence in {"daily", "weekly"}:
                        reminder.scheduled_at = next_occurrence(
                            reminder.scheduled_at, reminder.timezone, reminder.recurrence
                        )
                        reminder.status = "pending"
                        db.add(
                            JobRow(
                                user_id=reminder.user_id,
                                reminder_id=reminder.id,
                                scheduled_at=reminder.scheduled_at,
                                idempotency_key=(
                                    f"reminder:{reminder.id}:{reminder.scheduled_at.isoformat()}"
                                ),
                            )
                        )
                    else:
                        reminder.status = "delivered"
                    job.status = "succeeded"
                job.completed_at = now
                await db.commit()
                logger.info("job lifecycle job_id=%s status=%s", job.id, job.status)
                processed += 1
            except Exception as exc:
                await db.rollback()
                async with SessionLocal() as retry_db:
                    retry = await retry_db.get(JobRow, job_id)
                    if retry:
                        retry.last_error = type(exc).__name__
                        retry.status = "failed" if retry.attempts >= MAX_ATTEMPTS else "queued"
                        if retry.status == "queued":
                            retry.scheduled_at = now + timedelta(seconds=30 * retry.attempts)
                        else:
                            retry.completed_at = now
                            failed_reminder = (
                                await retry_db.get(ReminderRow, retry.reminder_id)
                                if retry.reminder_id
                                else None
                            )
                            if failed_reminder and failed_reminder.status == "pending":
                                failed_reminder.status = "failed"
                        await retry_db.commit()
                logger.exception("job execution failed job_id=%s", job_id)
    return processed


async def run_worker(poll_seconds: float = 2.0):
    while True:
        try:
            await run_due_once()
        except Exception:
            logger.exception("reminder worker poll failed")
        await asyncio.sleep(poll_seconds)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker())
