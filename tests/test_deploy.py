"""Deployment-related behaviour: DB URL normalisation and the optional API-key guard."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from claim_service.config import get_settings
from claim_service.db.engine import normalize_database_url
from claim_service.main import create_app
from tests.dbutil import database_url_for


def test_postgres_urls_use_psycopg_driver() -> None:
    assert normalize_database_url("postgres://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalize_database_url("postgresql://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalize_database_url("sqlite:///x.db") == "sqlite:///x.db"


@pytest.fixture
def keyed_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fresh_external_schema: None
) -> Iterator[TestClient]:
    monkeypatch.setenv("API_KEY", "secret-test-key")
    get_settings.cache_clear()
    app = create_app(database_url_for(tmp_path, "keyed.db"))
    with TestClient(app) as client:
        yield client
    monkeypatch.delenv("API_KEY")
    get_settings.cache_clear()


def test_health_stays_public_when_key_is_set(keyed_client: TestClient) -> None:
    assert keyed_client.get("/api/health").status_code == 200


def test_api_rejects_missing_or_wrong_key(keyed_client: TestClient) -> None:
    assert keyed_client.get("/api/catalog/rules").status_code == 401
    wrong = keyed_client.get("/api/catalog/rules", headers={"X-API-Key": "nope"})
    assert wrong.status_code == 401


def test_api_accepts_x_api_key_and_bearer(keyed_client: TestClient) -> None:
    by_header = keyed_client.get("/api/catalog/rules", headers={"X-API-Key": "secret-test-key"})
    assert by_header.status_code == 200
    by_bearer = keyed_client.get(
        "/api/catalog/rules", headers={"Authorization": "Bearer secret-test-key"}
    )
    assert by_bearer.status_code == 200
