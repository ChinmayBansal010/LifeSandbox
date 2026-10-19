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
        ("extracted_text_max_chars", 0),
        ("stt_max_bytes", 0),
        ("tts_max_chars", 0),
        ("rate_limit_per_minute", 0),
        ("embedding_dimensions", 0),
    ],
)
def test_positive_operational_limits_are_rejected(field, value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})


def test_timeout_must_be_positive():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, openrouter_timeout_seconds=-1)
