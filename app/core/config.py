from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    app_host: str = "0.0.0.0"
    app_port: int = Field(default=8000, ge=1, le=65535)
    log_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=list)
    database_url: str = "sqlite+aiosqlite:///./life_sandbox.db"
    auth_mode: Literal["development", "jwt"] = "development"
    auth_secret: str | None = None
    auth_issuer: str | None = None
    auth_audience: str | None = None
    admin_user_ids: list[str] = Field(default_factory=list)
    llm_provider: Literal["mock", "nebius", "openrouter"] = "mock"
    llm_fallback_provider: Literal["", "nebius", "openrouter", "mock"] = ""
    nebius_api_key: str | None = None
    nebius_base_url: str = "https://api.tokenfactory.nebius.com/v1"
    nebius_model: str = "nvidia/Nemotron-3_5-Lightning"
    openrouter_api_key: str | None = None
    openrouter_model: str = ""
    openrouter_fallback_model: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    mem0_api_key: str | None = None
    mem0_host: str = "https://api.mem0.ai"
    browser_use_enabled: bool = False
    llm_timeout_seconds: float = Field(default=30, gt=0, le=300)
    mem0_search_timeout_seconds: float = Field(default=10.0, gt=0, le=120)
    mem0_add_timeout_seconds: float = Field(default=10.0, gt=0, le=120)
    # Keep each model completion short enough that multi-step tool turns finish
    # before the browser's 105-second safety timeout. This applies to both
    # OpenAI-compatible providers (Nebius and OpenRouter).
    openrouter_timeout_seconds: float = Field(default=75.0, gt=0, le=300)
    chat_request_timeout_seconds: float = Field(default=95.0, gt=0, le=600)
    llm_max_tokens: int = Field(default=4096, ge=1, le=32768)
    research_provider: Literal["disabled", "tavily"] = "disabled"
    tavily_api_key: str | None = None
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None
    google_oauth_callback_url: str | None = None
    google_auth_callback_url: str | None = None
    google_auth_frontend_url: str = "http://localhost:5173"
    google_token_encryption_key: str | None = None
    google_oauth_redirect_uri: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    telegram_allowed_chat_ids: str | None = None
    telegram_default_user_id: str = "local-user"
    telegram_user_id_map: dict[str, str] = Field(default_factory=dict)
    telegram_polling_enabled: bool = True
    telegram_webhook_secret: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str = "us-east-2"
    aws_endpoint_url_s3: str | None = None
    neon_storage_bucket: str | None = None
    embedding_provider: Literal["fastembed", "openai", "local_hash"] = "fastembed"
    embedding_dimensions: int = Field(default=384, ge=8, le=8192)
    fastembed_model: str = "BAAI/bge-small-en-v1.5"
    openai_api_key: str | None = None
    openai_embedding_model: str = "text-embedding-3-small"
    upload_max_bytes: int = Field(default=10_000_000, ge=1, le=100_000_000)
    file_storage_dir: str = "./data/uploads"
    extracted_text_max_chars: int = Field(default=200_000, ge=1, le=2_000_000)
    stt_provider: Literal["disabled", "faster_whisper"] = "disabled"
    stt_model: str = "tiny"
    stt_device: str = "cpu"
    stt_compute_type: str = "int8"
    stt_max_bytes: int = Field(default=20_000_000, ge=1, le=100_000_000)
    stt_max_duration_seconds: int = Field(default=300, ge=1, le=3600)
    stt_timeout_seconds: float = Field(default=120, gt=0, le=600)
    tts_provider: Literal["disabled", "kokoro"] = "disabled"
    tts_max_chars: int = Field(default=5000, ge=1, le=50000)
    tts_voice: str = "af_heart"
    vision_enabled: bool = False
    image_max_bytes: int = Field(default=5_000_000, ge=1, le=100_000_000)
    rate_limit_per_minute: int = Field(default=60, ge=1, le=10000)
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
        if self.embedding_provider == "openai" and not (
            self.openai_api_key or self.nebius_api_key or self.openrouter_api_key
        ):
            raise ValueError("OpenAI embeddings require OPENAI_API_KEY")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
