"""Explicit, additive V2 migration with a database ownership guard."""

import argparse
import os
import sys
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Engine,
    ForeignKeyConstraint,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    create_engine,
    event,
    func,
    insert,
    inspect,
    select,
    text,
)
from sqlalchemy.pool import StaticPool

from claim_mcp_v2.config import SERVICE, Settings

SCHEMA_VERSION = 1
metadata = MetaData()
identity = Table(
    "v2_database_identity", metadata,
    Column("id", Integer, primary_key=True),
    Column("service", String(80), nullable=False),
    Column("project_id", String(100), nullable=False),
    Column("schema_version", Integer, nullable=False),
)
actors = Table(
    "v2_actors", metadata,
    Column("actor_id", String(36), primary_key=True),
    Column("display_name", String(100), nullable=False),
    Column("active", Boolean, nullable=False, default=True),
)
workspaces = Table(
    "v2_workspaces", metadata,
    Column("workspace_id", String(36), primary_key=True),
    Column("display_name", String(100), nullable=False),
    Column("active", Boolean, nullable=False, default=True),
)
memberships = Table(
    "v2_memberships", metadata,
    Column("membership_id", String(36), primary_key=True),
    Column("actor_id", String(36), nullable=False),
    Column("workspace_id", String(36), nullable=False),
    Column("active", Boolean, nullable=False, default=True),
    UniqueConstraint("actor_id", "workspace_id"),
    ForeignKeyConstraint(["actor_id"], ["v2_actors.actor_id"]),
    ForeignKeyConstraint(["workspace_id"], ["v2_workspaces.workspace_id"]),
)
credentials = Table(
    "v2_credentials", metadata,
    Column("key_id", String(36), primary_key=True),
    Column("membership_id", String(36), nullable=False),
    Column("key_hash", String(64), nullable=False, unique=True),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("revoked_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    ForeignKeyConstraint(["membership_id"], ["v2_memberships.membership_id"]),
)


class DatabaseBoundaryError(Exception):
    """A generic error safe to display without database details."""


def build_engine(settings: Settings) -> Engine:
    url = settings.sqlalchemy_url()
    kwargs: dict[str, object] = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url:
            kwargs["poolclass"] = StaticPool
    engine = create_engine(url, pool_pre_ping=True, hide_parameters=True, **kwargs)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection: object, _record: object) -> None:
            cursor = connection.cursor()  # type: ignore[attr-defined]
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine


def migrate(engine: Engine, project_id: str, app_role: str | None = None) -> None:
    with engine.begin() as conn:
        # Serialize release migrations across PostgreSQL instances/jobs.
        if engine.dialect.name == "postgresql":
            conn.execute(text("SELECT pg_advisory_xact_lock(70321002)"))
        existing = set(inspect(conn).get_table_names())
        if existing - set(metadata.tables):
            raise DatabaseBoundaryError("Refusing a non-V2 or non-empty unowned database")
        if existing and "v2_database_identity" not in existing:
            raise DatabaseBoundaryError("Refusing an unowned partial V2 database")
        if "v2_database_identity" in existing:
            row = conn.execute(select(identity)).mappings().first()
            if row is None or row["service"] != SERVICE or row["project_id"] != project_id:
                raise DatabaseBoundaryError("V2 database ownership check failed")
            if row["schema_version"] != SCHEMA_VERSION:
                raise DatabaseBoundaryError("Unsupported V2 schema version")
        metadata.create_all(conn)
        if not existing:
            conn.execute(insert(identity).values(
                id=1, service=SERVICE, project_id=project_id, schema_version=SCHEMA_VERSION,
            ))
        if app_role is not None:
            if app_role != "insurance_claim_v2_app" or engine.dialect.name != "postgresql":
                raise DatabaseBoundaryError("Unsupported V2 application role")
            # This infrastructure release only exposes read-only context tools.
            conn.execute(text("REVOKE CREATE ON SCHEMA public FROM PUBLIC"))
            conn.execute(text("GRANT USAGE ON SCHEMA public TO insurance_claim_v2_app"))
            for table in metadata.sorted_tables:
                conn.execute(text(f"GRANT SELECT ON {table.name} TO insurance_claim_v2_app"))
    check_ready(engine, project_id)


def check_ready(engine: Engine, project_id: str) -> None:
    with engine.connect() as conn:
        if set(inspect(conn).get_table_names()) != set(metadata.tables):
            raise DatabaseBoundaryError("V2 schema is missing or contains foreign tables")
        rows = conn.execute(select(identity)).mappings().all()
        if len(rows) != 1 or rows[0]["service"] != SERVICE:
            raise DatabaseBoundaryError("V2 database ownership check failed")
        if rows[0]["project_id"] != project_id or rows[0]["schema_version"] != SCHEMA_VERSION:
            raise DatabaseBoundaryError("V2 database version or project mismatch")


def utc_datetime(value: datetime) -> datetime:
    # SQLite returns a naive datetime even for a timezone-aware SQLAlchemy column.
    from datetime import UTC
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate only the dedicated V2 database")
    parser.add_argument("command", choices=["migrate", "check"])
    args = parser.parse_args()
    engine = None
    try:
        settings = Settings()
        engine = build_engine(settings)
        if args.command == "migrate":
            migrate(engine, settings.database_project_id, settings.database_app_role)
            if probe_key := os.environ.get("V2_SMOKE_KEY"):
                from claim_mcp_v2.admin import ensure_probe
                ensure_probe(engine, probe_key)
        else:
            check_ready(engine, settings.database_project_id)
        print("V2 database schema ready")
        return 0
    except Exception:
        print("V2 database operation failed; check configuration and ownership", file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
