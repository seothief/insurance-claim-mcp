import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.engine import make_url

from claim_mcp_v2.config import Settings
from claim_mcp_v2.db import build_engine, metadata, migrate


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        database_url=os.environ.get("V2_TEST_DATABASE_URL", f"sqlite:///{tmp_path}/test_v2.db"),
        database_project_id="test-v2",
        app_version="test-sha",
    )


@pytest.fixture
def engine(settings: Settings) -> Iterator[Engine]:
    url = make_url(settings.sqlalchemy_url())
    if url.drivername.startswith("postgresql"):
        socket = str(url.query.get("host", ""))
        test_socket = socket.startswith(str(Path.home() / ".cache")) and "/v2-pg-test-" in socket
        assert url.host in {"localhost", "127.0.0.1", "db-v2"} or test_socket, (
            "Use a local disposable test DB"
        )
    engine = build_engine(settings)
    # Never drop arbitrary externally supplied tables or use a production database in tests.
    if engine.dialect.name == "postgresql":
        assert settings.environment == "test"
        from sqlalchemy import inspect
        existing = set(inspect(engine).get_table_names())
        assert not existing - set(metadata.tables)
        if existing:
            from claim_mcp_v2.db import check_ready
            check_ready(engine, "test-v2")
        metadata.drop_all(engine)
    migrate(engine, settings.database_project_id)
    yield engine
    if engine.dialect.name == "postgresql":
        metadata.drop_all(engine)
    engine.dispose()
