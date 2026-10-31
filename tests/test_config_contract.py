import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_requires_jwt_authentication():
    with pytest.raises(ValidationError, match="Production requires AUTH_MODE=jwt"):
        Settings(app_env="production", auth_mode="development")


def test_jwt_requires_secret_and_claim_constraints():
    with pytest.raises(ValidationError, match="AUTH_SECRET"):
        Settings(auth_mode="jwt", auth_secret=None, auth_issuer="issuer", auth_audience="audience")


def test_provider_requires_key_and_model():
    with pytest.raises(ValidationError, match="requires its API key and model"):
        Settings(llm_provider="openrouter", openrouter_api_key=None, openrouter_model="model")
