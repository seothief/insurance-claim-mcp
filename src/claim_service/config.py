"""Application settings loaded from environment variables (and an optional .env file)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _default_db_path() -> Path:
    """Source checkout: <repo>/claim_service.db. Installed package: ~/.insurance-claim-mcp."""
    if (PROJECT_ROOT / "pyproject.toml").is_file():
        return PROJECT_ROOT / "claim_service.db"
    data_dir = Path.home() / ".insurance-claim-mcp"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "claim_service.db"


DEFAULT_DATABASE_URL = f"sqlite:///{_default_db_path().as_posix()}"


class Settings(BaseSettings):
    """Runtime settings. Set DATABASE_URL to a PostgreSQL URL for cloud deployment."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = DEFAULT_DATABASE_URL

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
