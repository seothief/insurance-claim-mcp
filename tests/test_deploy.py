"""Deployment checks for database URLs, health endpoints and per-user-key MCP HTTP access."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from claim_service.db.engine import create_db_engine, normalize_database_url
from claim_service.db.repository import PolicyRepository
from claim_service.domain.models import UserIn
from claim_service.domain.security import api_key_prefix, generate_api_key, hash_api_key
from claim_service.main import create_app
from tests.dbutil import database_url_for


def test_postgres_urls_use_psycopg_driver() -> None:
    assert normalize_database_url("postgres://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalize_database_url("postgresql://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalize_database_url("sqlite:///x.db") == "sqlite:///x.db"


@pytest.fixture
def keyed_client(
    tmp_path: Path, fresh_external_schema: None
) -> Iterator[tuple[TestClient, str]]:
    """App bound to a fresh DB with one user that owns an active key."""
    database_url = database_url_for(tmp_path, "keyed.db")
    with TestClient(create_app(database_url)) as client:
        engine = create_db_engine(database_url)
        repo = PolicyRepository(engine)
        repo.create_user(UserIn(user_id="seoth"))
        raw_key = generate_api_key()
        repo.create_api_key("seoth", hash_api_key(raw_key), api_key_prefix(raw_key))
        yield client, raw_key
        engine.dispose()


def test_health_and_version_remain_public(keyed_client: tuple[TestClient, str]) -> None:
    client, _ = keyed_client
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/version").json()["service"] == "insurance-claim-mcp"


def test_openapi_and_general_web_routes_are_not_served(
    keyed_client: tuple[TestClient, str],
) -> None:
    client, raw_key = keyed_client
    for path in ("/", "/openapi.json", "/llms.txt", "/about.md", "/start", "/ai/guide"):
        response = client.get(path, headers={"X-User-Key": raw_key})
        assert response.status_code == 404


def test_mcp_rejects_missing_or_wrong_key(keyed_client: tuple[TestClient, str]) -> None:
    client, _ = keyed_client
    assert client.post("/mcp", json={}).status_code == 401
    wrong = client.post("/mcp", headers={"X-User-Key": "nope"}, json={})
    assert wrong.status_code == 401


def test_mcp_rejects_user_mismatch_with_key(keyed_client: tuple[TestClient, str]) -> None:
    client, raw_key = keyed_client
    response = client.get("/mcp", headers={"X-User-Key": raw_key, "X-User-Id": "someone-else"})
    assert response.status_code == 401


def test_mcp_without_trailing_slash_does_not_redirect(
    keyed_client: tuple[TestClient, str],
) -> None:
    client, raw_key = keyed_client
    response = client.post(
        "/mcp",
        headers={
            "X-User-Key": raw_key,
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


def test_mcp_accepts_user_key_and_bearer(keyed_client: tuple[TestClient, str]) -> None:
    client, raw_key = keyed_client
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
        {"X-User-Key": raw_key},
        {"Authorization": f"Bearer {raw_key}"},
    ):
        response = client.post("/mcp", headers={**headers, **auth}, json=request)
        assert response.status_code == 200
