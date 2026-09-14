from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "JobPilot API"
    database_url: str = "postgresql+psycopg://jobpilot:jobpilot@postgres:5432/jobpilot"
    jwt_secret: str = "change-this-in-production"
    jwt_expire_minutes: int = 720
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    chat_model: str = "gpt-4o-mini"
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
    # Local Docker demo: one private workspace, no login screen required.
    # Set false before any public deployment to enforce JWT authentication.
    local_workspace_mode: bool = True
    upload_dir: Path = Path("/app/uploads")
    max_upload_mb: int = 8
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
