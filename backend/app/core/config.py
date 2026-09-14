from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "JobPilot API"
    database_url: str = "postgresql+psycopg://jobpilot:jobpilot@postgres:5432/jobpilot"
    jwt_secret: str = "change-this-in-production"
    jwt_expire_minutes: int = 720
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    chat_model: str = "gpt-4o-mini"
    # Dedicated embedding credentials avoid ever mixing a visitor's chat
    # provider with the developer-owned retrieval model. Legacy OPENAI_*
    # values remain a backward-compatible fallback for local installs.
    embedding_api_key: str | None = None
    embedding_base_url: str | None = None
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536
    # Keep inline execution for lightweight local development. Docker overrides
    # this to `queue` and delegates long-running Agent work to an RQ worker.
    task_mode: str = "inline"
    redis_url: str = "redis://redis:6379/0"
    analysis_job_timeout_seconds: int = 240
    # Optional provider pricing used only for developer-side cost estimates.
    chat_input_cost_per_million: float = 0.0
    chat_output_cost_per_million: float = 0.0
    knowledge_admin_key: str | None = None
    model_config_encryption_key: str | None = None
    # Local Docker demo: one private workspace, no login screen required.
    # Set false before any public deployment to enforce JWT authentication.
    local_workspace_mode: bool = True
    # Public, passwordless deployments use a signed HttpOnly cookie to map
    # every browser profile to a separate internal user/workspace.
    anonymous_workspace_mode: bool = False
    workspace_cookie_name: str = "jobpilot_workspace"
    workspace_cookie_secure: bool = False
    workspace_ttl_days: int = 30
    # Render supplies a plain `postgresql://` URL. The validator below pins it
    # to psycopg 3, which is the driver bundled by this project.
    serve_frontend: bool = False
    static_dir: Path = Path("/app/frontend-dist")
    allowed_origins: str = "http://localhost:5173"
    upload_dir: Path = Path("/app/uploads")
    max_upload_mb: int = 8
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("database_url", mode="before")
    @classmethod
    def use_psycopg_driver(cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        return value

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
