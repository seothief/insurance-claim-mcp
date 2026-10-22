"""Deployment checks for database URLs, health endpoints and MCP HTTP access."""

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


def test_health_and_version_remain_public(keyed_client: TestClient) -> None:
    assert keyed_client.get("/api/health").json() == {"status": "ok"}
    assert keyed_client.get("/api/version").json()["service"] == "insurance-claim-mcp"


def test_openapi_and_general_web_routes_are_not_served(keyed_client: TestClient) -> None:
    for path in ("/", "/openapi.json", "/llms.txt", "/about.md", "/start", "/ai/guide"):
        response = keyed_client.get(path, headers={"X-API-Key": "secret-test-key"})
        assert response.status_code == 404


def test_mcp_rejects_missing_or_wrong_key(keyed_client: TestClient) -> None:
    assert keyed_client.post("/mcp", json={}).status_code == 401
    wrong = keyed_client.post("/mcp", headers={"X-API-Key": "nope"}, json={})
    assert wrong.status_code == 401
    user_identity_is_not_auth = keyed_client.get(
        "/mcp",
        headers={"X-User-Id": "seoth", "X-User-Key": "legacy-user-key"},
    )
    assert user_identity_is_not_auth.status_code == 401



def test_mcp_without_trailing_slash_does_not_redirect(keyed_client: TestClient) -> None:
    response = keyed_client.post(
        "/mcp",
        headers={
            "X-API-Key": "secret-test-key",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        },
        follow_redirects=False,
    )
    assert response.status_code == 200


def test_mcp_accepts_x_api_key_and_bearer(keyed_client: TestClient) -> None:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1"},
        },
    }
    for auth in (
        {"X-API-Key": "secret-test-key"},
        {"Authorization": "Bearer secret-test-key"},
    ):
        response = keyed_client.post("/mcp", headers={**headers, **auth}, json=request)
        assert response.status_code == 200
