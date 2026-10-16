"""Shared test database setup.

By default tests use a temporary SQLite file. Set TEST_DATABASE_URL (for example to a PostgreSQL
URL in CI) to run the same tests against that database. Tables are dropped and recreated before
each test so every test starts from an empty schema.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from claim_service.config import get_settings
from claim_service.db.engine import create_db_engine, init_schema
from claim_service.db.tables import metadata
from claim_service.main import create_app
from tests.dbutil import database_url_for


@pytest.fixture
def fresh_external_schema() -> Iterator[None]:
    """Reset the external test database schema before a test that uses TEST_DATABASE_URL."""
    external = os.environ.get("TEST_DATABASE_URL")
    if external:
        engine = create_db_engine(external)
        metadata.drop_all(engine)
        init_schema(engine)
        engine.dispose()
    yield


@pytest.fixture
def client(
    tmp_path: Path, fresh_external_schema: None, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    """REST/MCP test client bound to a fresh database (SQLite by default, PostgreSQL in CI)."""
    monkeypatch.setenv("SEED_SAMPLE_DATA", "true")
    get_settings.cache_clear()
    with TestClient(create_app(database_url_for(tmp_path, "test.db"))) as test_client:
        yield test_client
    get_settings.cache_clear()
