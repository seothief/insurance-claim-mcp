"""Small Google Secret Manager helpers shared by operational scripts."""

from __future__ import annotations

import base64

import httpx

PROJECT_ID = "project-93d02748-0cbc-4596-902"
SECRET_MANAGER_API = "https://secretmanager.googleapis.com/v1"


def get_secret_text(token: str, secret_name: str, project_id: str = PROJECT_ID) -> str:
    """Read and decode a Secret Manager value without exposing it in errors."""
    response = httpx.get(
        f"{SECRET_MANAGER_API}/projects/{project_id}/secrets/"
        f"{secret_name}/versions/latest:access",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15.0,
    )
    response.raise_for_status()
    encoded: str = response.json()["payload"]["data"]
    return base64.b64decode(encoded).decode("utf-8").strip()


def get_database_url(token: str, project_id: str = PROJECT_ID) -> str:
    """Read the service database URL from Secret Manager."""
    database_url = get_secret_text(token, "DATABASE_URL", project_id)
    if database_url.startswith(("postgres://", "postgresql://")):
        prefix = "postgres://" if database_url.startswith("postgres://") else "postgresql://"
        database_url = "postgresql+psycopg://" + database_url[len(prefix) :]
    return database_url