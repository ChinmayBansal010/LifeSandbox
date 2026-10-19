import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_development_defaults_are_local_and_credential_free():
    settings = Settings(_env_file=None)
    assert settings.app_env == "development"
    assert settings.auth_mode == "development"
    assert settings.llm_provider == "mock"


def test_production_requires_jwt_authentication():
    with pytest.raises(ValidationError, match="Production requires AUTH_MODE=jwt"):
        Settings(_env_file=None, app_env="production", auth_mode="development")


def test_jwt_requires_secret_issuer_and_audience():
    with pytest.raises(ValidationError, match="AUTH_SECRET is required"):
        Settings(_env_file=None, auth_mode="jwt")
    with pytest.raises(ValidationError, match="AUTH_ISSUER and AUTH_AUDIENCE are required"):
        Settings(_env_file=None, auth_mode="jwt", auth_secret="test-secret")


@pytest.mark.parametrize("provider", ["nebius", "openrouter"])
def test_selected_model_provider_requires_key_and_model(provider):
    with pytest.raises(ValidationError, match=f"{provider} requires its API key and model"):
        Settings(_env_file=None, llm_provider=provider)


def test_tavily_research_requires_api_key():
    with pytest.raises(ValidationError, match="TAVILY_API_KEY is required"):
        Settings(_env_file=None, research_provider="tavily")


def test_configured_provider_accepts_complete_credentials():
    settings = Settings(
        _env_file=None,
        llm_provider="openrouter",
        openrouter_api_key="test-key",
        openrouter_model="test-model",
    )
    assert settings.llm_provider == "openrouter"
