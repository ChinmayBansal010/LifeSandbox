import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.persistence.models import JobRow, NotificationRow, ReminderRow
from app.persistence.session import SessionLocal

logger = logging.getLogger("life_sandbox.jobs")


async def run_due_once(now: datetime | None = None, limit: int = 25) -> int:
    """Claim and deliver due reminders. The unique job notification prevents duplicates."""
    now = now or datetime.now(UTC)
    processed = 0
    async with SessionLocal() as db:
        ids = list(
            (
                await db.scalars(
                    select(JobRow.id)
                    .where(
                        JobRow.job_type == "reminder_delivery",
                        JobRow.status == "queued",
                        JobRow.scheduled_at <= now,
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
                .where(JobRow.id == job_id, JobRow.status == "queued")
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
                        retry.attempts += 1
                        retry.last_error = type(exc).__name__
                        retry.status = "failed" if retry.attempts >= 3 else "queued"
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
        await run_due_once()
        await asyncio.sleep(poll_seconds)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker())
