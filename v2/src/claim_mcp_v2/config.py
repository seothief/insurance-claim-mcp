"""V2-only configuration; intentionally ignores V1 DATABASE_URL and APP_VERSION."""

from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

SERVICE = "insurance-claim-mcp-v2"
DATABASE_NAME = "insurance_claim_v2"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="V2_", extra="ignore", env_file=None, hide_input_in_errors=True,
    )

    environment: Literal["development", "test", "production"] = "development"
    database_url: SecretStr = SecretStr("sqlite:///./claim_service_v2.db")
    app_version: str = "local"
    database_project_id: str = "local"
    database_app_role: Literal["insurance_claim_v2_app"] | None = None

    @model_validator(mode="after")
    def check_database(self) -> "Settings":
        try:
            url = make_url(self.database_url.get_secret_value())
        except Exception:
            raise ValueError("Invalid V2 database configuration") from None
        if url.drivername not in {"sqlite", "postgresql", "postgresql+psycopg"}:
            raise ValueError("Unsupported V2 database driver")
        if url.drivername == "sqlite":
            if self.environment == "production":
                raise ValueError("Production V2 requires its own PostgreSQL database")
            database = url.database
            if database and database != ":memory:" and "v2" not in database.lower():
                raise ValueError("Local database filename must identify V2")
        elif url.database != DATABASE_NAME:
            raise ValueError("V2 requires the dedicated insurance_claim_v2 database")
        if self.environment == "production":
            if not self.database_project_id or self.database_project_id == "local":
                raise ValueError("V2_DATABASE_PROJECT_ID must identify the separate Neon project")
            if url.query.get("sslmode") != "verify-full":
                raise ValueError("Production V2 requires certificate-verified PostgreSQL TLS")
        return self

    def sqlalchemy_url(self) -> str:
        url = make_url(self.database_url.get_secret_value())
        if url.drivername == "postgresql":
            url = url.set(drivername="postgresql+psycopg")
        return url.render_as_string(hide_password=False)
