from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=list)
    database_url: str = "sqlite+aiosqlite:///./life_sandbox.db"
    auth_mode: Literal["development", "jwt"] = "development"
    auth_secret: str | None = None
    auth_issuer: str | None = None
    auth_audience: str | None = None
    llm_provider: Literal["mock", "nebius", "openrouter"] = "mock"
    llm_fallback_provider: Literal["", "nebius", "openrouter"] = ""
    nebius_api_key: str | None = None
    nebius_base_url: str = "https://api.tokenfactory.nebius.com/v1"
    nebius_model: str = ""
    openrouter_api_key: str | None = None
    openrouter_model: str = ""
    openrouter_fallback_model: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    mem0_api_key: str | None = None
    mem0_host: str = "https://api.mem0.ai"
    browser_use_enabled: bool = False
    llm_timeout_seconds: float = 30
    llm_max_tokens: int = 1000
    research_provider: Literal["disabled", "tavily"] = "disabled"
    tavily_api_key: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str = "us-east-2"
    aws_endpoint_url_s3: str | None = None
    neon_storage_bucket: str | None = None
    embedding_provider: Literal["local_hash"] = "local_hash"
    embedding_dimensions: int = 128
    upload_max_bytes: int = 10_000_000
    rate_limit_per_minute: int = 60
    langsmith_tracing: bool = False
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"
    sentry_dsn: str | None = None

    @model_validator(mode="after")
    def selected_provider_is_configured(self):
        if self.app_env == "production" and self.auth_mode != "jwt":
            raise ValueError("Production requires AUTH_MODE=jwt")
        if self.auth_mode == "jwt":
            if not self.auth_secret:
                raise ValueError("AUTH_SECRET is required when AUTH_MODE=jwt")
            if not self.auth_issuer or not self.auth_audience:
                raise ValueError("AUTH_ISSUER and AUTH_AUDIENCE are required when AUTH_MODE=jwt")
        selected = {
            "nebius": (self.nebius_api_key, self.nebius_model),
            "openrouter": (self.openrouter_api_key, self.openrouter_model),
        }
        if self.llm_provider in selected and not all(selected[self.llm_provider]):
            raise ValueError(f"{self.llm_provider} requires its API key and model")
        if self.research_provider == "tavily" and not self.tavily_api_key:
            raise ValueError("TAVILY_API_KEY is required when RESEARCH_PROVIDER=tavily")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
