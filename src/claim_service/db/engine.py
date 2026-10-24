"""Engine creation and schema initialisation."""

from sqlalchemy import Engine, create_engine, event, inspect, text

from claim_service.db.tables import metadata


def normalize_database_url(database_url: str) -> str:
    """Use the psycopg 3 driver for PostgreSQL URLs (cloud providers often emit postgres://)."""
    if database_url.startswith("postgres://"):
        return "postgresql+psycopg://" + database_url[len("postgres://") :]
    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + database_url[len("postgresql://") :]
    return database_url


def create_db_engine(database_url: str) -> Engine:
    database_url = normalize_database_url(database_url)
    connect_args: dict[str, object] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    engine = create_engine(
        database_url,
        connect_args=connect_args,
        future=True,
        pool_pre_ping=not database_url.startswith("sqlite"),
    )

    if database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_conn: object, _record: object) -> None:
            cursor = dbapi_conn.cursor()  # type: ignore[attr-defined]
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def init_schema(engine: Engine) -> None:
    metadata.create_all(engine)
    # Lightweight additive migrations for databases created before a column existed.
    with engine.begin() as conn:
        columns = {col["name"] for col in inspect(conn).get_columns("users")}
        if "pin_hash" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN pin_hash VARCHAR(128)"))
    with engine.begin() as conn:
        policy_columns = {col["name"] for col in inspect(conn).get_columns("user_policies")}
        if "source_type" not in policy_columns:
            conn.execute(
                text(
                    "ALTER TABLE user_policies "
                    "ADD COLUMN source_type VARCHAR(32) NOT NULL DEFAULT 'USER_STATED'"
                )
            )
        if "issuer" not in policy_columns:
            conn.execute(text("ALTER TABLE user_policies ADD COLUMN issuer VARCHAR(100)"))
        if "issued_on" not in policy_columns:
            conn.execute(text("ALTER TABLE user_policies ADD COLUMN issued_on VARCHAR(10)"))
    with engine.begin() as conn:
        rider_columns = {col["name"] for col in inspect(conn).get_columns("user_policy_riders")}
        if "source_type" not in rider_columns:
            conn.execute(
                text(
                    "ALTER TABLE user_policy_riders "
                    "ADD COLUMN source_type VARCHAR(32) NOT NULL DEFAULT 'USER_STATED'"
                )
            )
        if "issuer" not in rider_columns:
            conn.execute(text("ALTER TABLE user_policy_riders ADD COLUMN issuer VARCHAR(100)"))
        if "issued_on" not in rider_columns:
            conn.execute(text("ALTER TABLE user_policy_riders ADD COLUMN issued_on VARCHAR(10)"))
    with engine.begin() as conn:
        dialect = conn.dialect.name
        timestamp_type = "TIMESTAMP WITH TIME ZONE" if dialect == "postgresql" else "TIMESTAMP"
        key_columns = {col["name"] for col in inspect(conn).get_columns("user_api_keys")}
        # A legacy per-user key table (removed 2026-10-17) used `token_hash` and had no
        # prefix/lifecycle columns. Migrate in place instead of dropping stored keys.
        if "token_hash" in key_columns and "key_hash" not in key_columns:
            conn.execute(
                text("ALTER TABLE user_api_keys RENAME COLUMN token_hash TO key_hash")
            )
            key_columns.discard("token_hash")
            key_columns.add("key_hash")
        if "key_prefix" not in key_columns:
            conn.execute(
                text(
                    "ALTER TABLE user_api_keys "
                    "ADD COLUMN key_prefix VARCHAR(16) NOT NULL DEFAULT ''"
                )
            )
        if "note" not in key_columns:
            conn.execute(text("ALTER TABLE user_api_keys ADD COLUMN note VARCHAR(200)"))
        if "last_used_at" not in key_columns:
            conn.execute(
                text(f"ALTER TABLE user_api_keys ADD COLUMN last_used_at {timestamp_type}")
            )
        if "revoked_at" not in key_columns:
            conn.execute(
                text(f"ALTER TABLE user_api_keys ADD COLUMN revoked_at {timestamp_type}")
            )
    with engine.begin() as conn:
        rider_override_columns = {
            col["name"] for col in inspect(conn).get_columns("user_policy_riders")
        }
        if "rule_config_override" not in rider_override_columns:
            conn.execute(
                text("ALTER TABLE user_policy_riders ADD COLUMN rule_config_override JSON")
            )
