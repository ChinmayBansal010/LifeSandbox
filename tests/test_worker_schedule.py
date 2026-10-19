from datetime import UTC, datetime
from app.jobs.worker import next_occurrence

def test_daily_occurrence_advances_one_local_calendar_day():
    scheduled=datetime(2026,10,20,7,0,tzinfo=UTC)
    assert next_occurrence(scheduled,"UTC","daily") == datetime(2026,10,21,7,0,tzinfo=UTC)

def test_weekly_occurrence_advances_seven_days():
    scheduled=datetime(2026,10,20,7,0,tzinfo=UTC)
    assert next_occurrence(scheduled,"UTC","weekly") == datetime(2026,10,27,7,0,tzinfo=UTC)

def test_occurrence_keeps_local_wall_clock_across_offset():
    scheduled=datetime(2026,10,20,3,30,tzinfo=UTC)
    result=next_occurrence(scheduled,"Asia/Kolkata","daily")
    assert result.hour == 3 and result.minute == 30

import asyncio
import pytest
from app.jobs.worker import run_due_once

@pytest.mark.parametrize("limit", [0, -1, 101])
def test_worker_rejects_invalid_batch_size(limit):
    with pytest.raises(ValueError, match="between 1 and 100"):
        asyncio.run(run_due_once(limit=limit))
