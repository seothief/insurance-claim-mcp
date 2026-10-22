"""Application settings loaded from environment variables (and an optional .env file)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_URL = f"sqlite:///{(PROJECT_ROOT / 'claim_service.db').as_posix()}"


class Settings(BaseSettings):
    """Runtime settings. Set DATABASE_URL to a PostgreSQL URL for cloud deployment."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = DEFAULT_DATABASE_URL
    # When set, every /mcp request must send it as X-API-Key or Bearer token.
    # Leave empty for local development.
    api_key: str = ""

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
