import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, inspect, select, text, update
from sqlalchemy.exc import DBAPIError

from claim_mcp_v2.admin import PROBE_WORKSPACE_ID, bootstrap, ensure_probe
from claim_mcp_v2.config import Settings
from claim_mcp_v2.db import (
    DatabaseBoundaryError,
    build_engine,
    check_ready,
    credentials,
    identity,
    memberships,
    migrate,
)
from claim_mcp_v2.main import create_app
from claim_mcp_v2.security import authenticate, current_identity


def test_settings_ignore_v1_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://v1:secret@v1/neondb")
    monkeypatch.setenv("APP_VERSION", "v1-production")
    assert Settings().sqlalchemy_url() == "sqlite:///./claim_service_v2.db"
    assert Settings().app_version == "local"


@pytest.mark.parametrize("url", [
    "sqlite:///claim_service.db", "postgresql://u:p@localhost/neondb",
])
def test_reject_v1_database_names(url: str) -> None:
    with pytest.raises(ValueError):
        Settings(database_url=url)


def test_production_requires_dedicated_database_and_tls() -> None:
    with pytest.raises(ValueError):
        Settings(environment="production")
    with pytest.raises(ValueError):
        Settings(environment="production", database_project_id="new-neon-project",
                 database_url="postgresql://u:p@host/insurance_claim_v2?sslmode=require")
    config = Settings(environment="production", database_project_id="new-neon-project",
                      database_url="postgresql://u:p@host/insurance_claim_v2?sslmode=verify-full")
    assert config.sqlalchemy_url().startswith("postgresql+psycopg://")
    assert "u:p@" not in repr(config)


def test_migration_is_idempotent_and_bound_to_project(engine: Engine, settings: Settings) -> None:
    migrate(engine, settings.database_project_id)
    check_ready(engine, settings.database_project_id)
    with pytest.raises(DatabaseBoundaryError):
        migrate(engine, "another-neon-project")
    with engine.connect() as conn:
        assert len(conn.execute(select(identity)).all()) == 1


def test_never_migrate_a_v1_database(tmp_path: object) -> None:
    config = Settings(database_url="sqlite:///:memory:")
    engine = build_engine(config)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE users (user_id TEXT PRIMARY KEY)"))
    with pytest.raises(DatabaseBoundaryError):
        migrate(engine, "new-project")
    assert inspect(engine).get_table_names() == ["users"]
    engine.dispose()


def test_credentials_expire_revoke_and_follow_membership(engine: Engine) -> None:
    first = bootstrap(engine, "first", "agent")
    second = bootstrap(engine, "second", "agent")
    assert first["api_key"] != second["api_key"]
    who = authenticate(engine, first["api_key"])
    assert who is not None and who.workspace_id == first["workspace_id"]
    with engine.begin() as conn:
        conn.execute(update(credentials).where(credentials.c.key_id == first["key_id"]).values(
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        ))
    assert authenticate(engine, first["api_key"]) is None
    with engine.begin() as conn:
        conn.execute(update(memberships).where(
            memberships.c.membership_id == second["membership_id"],
        ).values(active=False))
    assert authenticate(engine, second["api_key"]) is None
    third = bootstrap(engine, "third", "agent")
    with engine.begin() as conn:
        conn.execute(update(credentials).where(credentials.c.key_id == third["key_id"]).values(
            revoked_at=datetime.now(UTC),
        ))
    assert authenticate(engine, third["api_key"]) is None
    with engine.connect() as conn:
        for row in conn.execute(select(credentials)).mappings():
            assert not row["key_hash"].startswith("icv2_")
            assert first["api_key"] not in str(row)


def test_release_probe_is_idempotent_and_separate_from_operators(engine: Engine) -> None:
    raw = "icv2_" + "synthetic-probe-key" * 3
    operator = bootstrap(engine, "operator-workspace", "agent")
    ensure_probe(engine, raw)
    ensure_probe(engine, raw)
    who = authenticate(engine, raw)
    assert who is not None and who.workspace_id == PROBE_WORKSPACE_ID
    assert who.workspace_id != operator["workspace_id"]
    with pytest.raises(ValueError, match="rotation"):
        ensure_probe(engine, raw + "changed")


def test_postgres_runtime_role_cannot_write_or_create_tables(engine: Engine) -> None:
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL privilege test")
    with engine.begin() as conn:
        if conn.execute(text(
            "SELECT 1 FROM pg_roles WHERE rolname = 'insurance_claim_v2_app'",
        )).first() is None:
            conn.execute(text("CREATE ROLE insurance_claim_v2_app NOLOGIN"))
    migrate(engine, "test-v2", "insurance_claim_v2_app")
    for statement in [
        "UPDATE v2_database_identity SET schema_version=99",
        "CREATE TABLE should_not_exist (id INTEGER)",
    ]:
        with engine.connect() as conn:
            transaction = conn.begin()
            try:
                conn.execute(text("SET LOCAL ROLE insurance_claim_v2_app"))
                assert conn.execute(select(identity.c.schema_version)).scalar() == 1
                with pytest.raises(DBAPIError):
                    conn.execute(text(statement))
            finally:
                transaction.rollback()


def rpc(client: TestClient, key: str, method: str, params: dict) -> dict:
    response = client.post("/mcp", headers={
        "Authorization": "Bearer " + key, "Accept": "application/json, text/event-stream",
    }, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        follow_redirects=False)
    assert response.status_code == 200
    assert "location" not in response.headers
    raw = response.text
    if raw.startswith(("event:", "data:")):
        raw = next(line[6:] for line in raw.splitlines() if line.startswith("data: "))
    return json.loads(raw)


def test_isolated_server_authentication_and_mcp(engine: Engine, settings: Settings) -> None:
    account = bootstrap(engine, "workspace", "agent")
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health").json()["service"] == "insurance-claim-mcp-v2"
        assert client.get("/api/ready").status_code == 200
        assert client.get("/api/version").json()["version"] == "test-sha"
        assert client.post("/mcp", json={}).status_code == 401
        assert client.post("/mcp", headers={
            "Authorization": "Bearer old-v1-key",
        }).status_code == 401
        headers = {"Authorization": "Bearer " + account["api_key"]}
        assert client.get("/openapi.json", headers=headers).status_code == 404
        assert client.post("/mcp", headers={**headers, "X-User-Id": "someone"}).status_code == 401
        result = rpc(client, account["api_key"], "initialize", {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "v2-tests", "version": "1"},
        })
        assert "error" not in result
        tools = rpc(client, account["api_key"], "tools/list", {})
        assert [t["name"] for t in tools["result"]["tools"]] == ["get_workspace_context"]
        result = rpc(client, account["api_key"], "tools/call", {
            "name": "get_workspace_context", "arguments": {},
        })
        assert not result["result"].get("isError", False)
        context = result["result"]["structuredContent"]
        assert context["workspace_id"] == account["workspace_id"]
        assert context["business_tools_available"] is False
        assert account["api_key"] not in json.dumps(result)
        assert current_identity.get() is None
        with engine.begin() as conn:
            conn.execute(update(credentials).where(
                credentials.c.key_id == account["key_id"],
            ).values(revoked_at=datetime.now(UTC)))
        assert client.post("/mcp", headers=headers, json={}).status_code == 401


def test_unmigrated_database_does_not_auto_initialize(tmp_path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path}/empty_v2.db")
    with pytest.raises(RuntimeError, match="V2 database not ready"):
        with TestClient(create_app(settings)):
            pass
    engine = build_engine(settings)
    assert inspect(engine).get_table_names() == []
    engine.dispose()
