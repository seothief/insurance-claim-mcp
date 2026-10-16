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


def test_openapi_schema_is_public_but_data_is_not(keyed_client: TestClient) -> None:
    schema = keyed_client.get("/openapi.json")
    assert schema.status_code == 200
    assert schema.json()["openapi"].startswith("3.1")
    assert keyed_client.get("/api/users/user_123/policies").status_code == 401


def test_openapi_lists_servers_when_public_url_is_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fresh_external_schema: None
) -> None:
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://example.test/")
    get_settings.cache_clear()
    with TestClient(create_app(database_url_for(tmp_path, "srv.db"))) as client:
        assert client.get("/openapi.json").json()["servers"] == [{"url": "https://example.test"}]
    monkeypatch.delenv("PUBLIC_BASE_URL")
    get_settings.cache_clear()


def test_start_guide_uses_public_base_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fresh_external_schema: None
) -> None:
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://example.test/")
    get_settings.cache_clear()
    with TestClient(create_app(database_url_for(tmp_path, "start-url.db"))) as client:
        assert "https://example.test/mcp" in client.get("/start.md").text
        assert "https://example.test/openapi.json" in client.get("/start.md").text
        assert "https://example.test/start" in client.get("/").text
        assert "https://example.test/start" in client.get("/llms.txt").text
    monkeypatch.delenv("PUBLIC_BASE_URL")
    get_settings.cache_clear()


def test_api_rejects_missing_or_wrong_key(keyed_client: TestClient) -> None:
    assert keyed_client.get("/api/catalog/rules").status_code == 401
    wrong = keyed_client.get("/api/catalog/rules", headers={"X-API-Key": "nope"})
    assert wrong.status_code == 401
    user_identity_is_not_auth = keyed_client.get(
        "/api/catalog/rules",
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


def test_api_accepts_x_api_key_and_bearer(keyed_client: TestClient) -> None:
    by_header = keyed_client.get("/api/catalog/rules", headers={"X-API-Key": "secret-test-key"})
    assert by_header.status_code == 200
    by_bearer = keyed_client.get(
        "/api/catalog/rules", headers={"Authorization": "Bearer secret-test-key"}
    )
    assert by_bearer.status_code == 200


def test_pin_protected_user_blocks_wrong_pin_and_allows_correct_pin(
    keyed_client: TestClient,
) -> None:
    headers = {"X-API-Key": "secret-test-key"}
    created = keyed_client.post(
        "/api/users",
        headers=headers,
        json={"user_id": "seoth", "display_alias": "본인", "pin": "4829"},
    )
    assert created.status_code == 201
    assert created.json()["pin_protected"] is True

    # Missing or wrong PIN is rejected with 403
    assert keyed_client.get("/api/users/seoth", headers=headers).status_code == 403
    assert keyed_client.get("/api/users/seoth?pin=0000", headers=headers).status_code == 403

    # Correct PIN via query or X-User-Pin header succeeds
    assert keyed_client.get("/api/users/seoth?pin=4829", headers=headers).status_code == 200
    header_pin = {**headers, "X-User-Pin": "4829"}
    assert keyed_client.get("/api/users/seoth", headers=header_pin).status_code == 200


def test_bound_user_header_prevents_cross_user_access(keyed_client: TestClient) -> None:
    bound_headers = {"X-API-Key": "secret-test-key", "X-User-Id": "seoth"}
    assert keyed_client.get("/api/users/user_123", headers=bound_headers).status_code == 403
