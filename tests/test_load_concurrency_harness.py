"""Concurrency, Load & Stress Testing Harness.

Tests rate limiting under high concurrent burst conditions, worker distributed
lease contention, and concurrent database operations.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.rate_limit import SlidingWindowRateLimiter
from app.jobs.worker import run_due_once
from app.persistence.models import Base, JobRow, ReminderRow
from app.persistence.session import SessionLocal, engine


@pytest.fixture(autouse=True)
async def init_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ─── 1. Rate Limiter Concurrency & Burst Harness ─────────────────────────────


@pytest.mark.asyncio
async def test_rate_limiter_burst_concurrency_harness():
    """Harness: test that rate limiter enforces exact limits under concurrent burst traffic."""
    limit = 25
    limiter = SlidingWindowRateLimiter(limit=limit, window_seconds=2.0)
    client_key = "concurrent-client-123"

    async def hit_limiter():
        return limiter.allow(client_key)

    # Fire 100 concurrent requests across tasks
    tasks = [asyncio.create_task(hit_limiter()) for _ in range(100)]
    results = await asyncio.gather(*tasks)

    allowed_count = sum(1 for r in results if r is True)
    blocked_count = sum(1 for r in results if r is False)

    # Exactly `limit` requests must be allowed, the rest blocked
    assert allowed_count == limit
    assert blocked_count == 75

    # After window expiration, capacity must be restored
    await asyncio.sleep(2.1)
    assert limiter.allow(client_key) is True


@pytest.mark.asyncio
async def test_rate_limiter_multi_tenant_isolation_under_load():
    """Harness: ensure distinct client keys don't starve or interfere with each other."""
    limiter = SlidingWindowRateLimiter(limit=10, window_seconds=2.0)
    clients = [f"client-{i}" for i in range(10)]

    async def burst_client(client_id: str):
        # Each client makes 15 attempts
        return [limiter.allow(client_id) for _ in range(15)]

    results = await asyncio.gather(*[burst_client(c) for c in clients])

    for client_results in results:
        # Every client gets exactly 10 allowed and 5 blocked
        assert sum(1 for r in client_results if r is True) == 10
        assert sum(1 for r in client_results if r is False) == 5


# ─── 2. Worker Distributed Lease Contention Harness ──────────────────────────


@pytest.mark.asyncio
async def test_worker_distributed_lease_contention_harness():
    """Harness: multiple workers competing concurrently for pending jobs must not double-execute."""
    user_id = f"contention-user-{uuid4().hex[:8]}"
    now_dt = datetime.now(UTC)
    scheduled_past = now_dt - timedelta(seconds=100)

    # Seed 10 due reminder jobs
    async with SessionLocal() as session:
        for i in range(10):
            reminder = ReminderRow(
                user_id=user_id,
                text=f"Reminder {i}",
                scheduled_at=scheduled_past,
                status="pending",
                recurrence="none",
                timezone="UTC",
            )
            session.add(reminder)
            await session.flush()
            job = JobRow(
                user_id=user_id,
                reminder_id=reminder.id,
                job_type="reminder_delivery",
                payload="{}",
                status="queued",
                scheduled_at=scheduled_past,
                idempotency_key=f"contention-job-{uuid4().hex}",
            )
            session.add(job)
        await session.commit()

    # Simulate 5 concurrent worker processes racing to execute the batch
    async def worker_iteration(worker_id: str):
        return await run_due_once(now=now_dt, limit=10)

    workers = [worker_iteration(f"worker-{i}") for i in range(5)]
    results = await asyncio.gather(*workers)

    total_processed = sum(results)
    assert total_processed == 10, f"Expected exactly 10 jobs processed, but got {total_processed}"

    # Verify database state: all 10 jobs are succeeded, none duplicated
    async with SessionLocal() as session:
        jobs = (await session.scalars(select(JobRow).where(JobRow.user_id == user_id))).all()
        assert len(jobs) == 10
        assert all(j.status == "succeeded" for j in jobs)


@pytest.mark.asyncio
async def test_idempotency_collision_under_concurrency():
    """Harness: concurrent job creation with same idempotency key must not corrupt state."""
    from sqlalchemy.exc import IntegrityError

    key = f"unique-idempotency-{uuid4().hex}"
    user_id = f"user-{uuid4().hex[:8]}"

    async def attempt_insert():
        try:
            async with SessionLocal() as session:
                job = JobRow(
                    user_id=user_id,
                    job_type="reminder_delivery",
                    payload="{}",
                    status="queued",
                    scheduled_at=datetime.now(UTC),
                    idempotency_key=key,
                )
                session.add(job)
                await session.commit()
                return "success"
        except IntegrityError:
            return "collision"

    results = await asyncio.gather(*[attempt_insert() for _ in range(5)])
    success_count = sum(1 for r in results if r == "success")
    collision_count = sum(1 for r in results if r == "collision")

    assert success_count == 1
    assert collision_count == 4

    # Clean up test job so it does not leave a pending job in shared test db
    from sqlalchemy import delete

    async with SessionLocal() as session:
        await session.execute(delete(JobRow).where(JobRow.idempotency_key == key))
        await session.commit()


