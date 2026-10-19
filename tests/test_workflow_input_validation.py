import pytest
from pydantic import ValidationError
from app.api.workflow import ReminderSchedule, TaskAction

def test_task_due_date_requires_timezone():
    with pytest.raises(ValidationError, match="timezone"):
        TaskAction(title="Prepare report",due_at="2026-10-20T09:00:00")

def test_task_rejects_unknown_timezone():
    with pytest.raises(ValidationError, match="IANA timezone"):
        TaskAction(title="Prepare report",timezone="Mars/Olympus")

def test_reminder_normalizes_timestamp_to_utc():
    reminder=ReminderSchedule(text="Review project",scheduled_at="2026-10-20T12:00:00+05:30",timezone="Asia/Kolkata")
    assert reminder.scheduled_at.isoformat() == "2026-10-20T06:30:00+00:00"

def test_reminder_rejects_unknown_recurrence():
    with pytest.raises(ValidationError):
        ReminderSchedule(text="Review project",scheduled_at="2026-10-20T12:00:00Z",recurrence="hourly")
