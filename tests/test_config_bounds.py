import pytest
from pydantic import ValidationError

from app.core.config import Settings


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("app_port", 0),
        ("app_port", 70000),
        ("llm_timeout_seconds", 0),
        ("llm_max_tokens", 0),
        ("upload_max_bytes", 0),
        ("upload_max_bytes", 100_000_001),
        ("extracted_text_max_chars", 0),
        ("stt_max_bytes", 0),
        ("stt_max_duration_seconds", 3601),
        ("tts_max_chars", 0),
        ("rate_limit_per_minute", 0),
        ("embedding_dimensions", 0),
        ("embedding_dimensions", 8193),
        ("image_max_bytes", 0),
    ],
)
def test_operational_limits_reject_out_of_range_values(field, value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})


@pytest.mark.parametrize(
    "field",
    [
        "llm_timeout_seconds",
        "mem0_search_timeout_seconds",
        "mem0_add_timeout_seconds",
        "openrouter_timeout_seconds",
        "chat_request_timeout_seconds",
        "stt_timeout_seconds",
    ],
)
def test_timeouts_must_be_positive(field):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: -1})
