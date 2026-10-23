"""Tests for additive database migrations on existing local schemas."""

from pathlib import Path

from sqlalchemy import inspect, text

from claim_service.db.engine import create_db_engine, init_schema
from claim_service.db.repository import PolicyRepository
from claim_service.db.tables import metadata
from claim_service.domain.security import api_key_prefix, hash_api_key


def test_policy_source_migration_adds_columns_and_marks_existing_rows_user_stated(
    tmp_path: Path,
) -> None:
    engine = create_db_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    metadata.create_all(engine)

    # Simulate a database created before policy and rider source metadata existed.
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE user_policies DROP COLUMN source_type"))
        connection.execute(text("ALTER TABLE user_policies DROP COLUMN issuer"))
        connection.execute(text("ALTER TABLE user_policies DROP COLUMN issued_on"))
        connection.execute(text("ALTER TABLE user_policy_riders DROP COLUMN source_type"))
        connection.execute(text("ALTER TABLE user_policy_riders DROP COLUMN issuer"))
        connection.execute(text("ALTER TABLE user_policy_riders DROP COLUMN issued_on"))
        connection.execute(text("INSERT INTO users (user_id) VALUES ('legacy-user')"))
        connection.execute(
            text(
                "INSERT INTO user_policies "
                "(policy_id, user_id, company, product_name, policy_type, is_active) "
                "VALUES ('legacy-policy', 'legacy-user', '보험사', '구형 보험', 'OTHER', 1)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO user_policy_riders "
                "(rider_id, policy_id, rider_name, coverage_amount, mapping_status) "
                "VALUES ('legacy-rider', 'legacy-policy', '기존 특약', 100000, 'MAPPED')"
            )
        )

    init_schema(engine)

    with engine.connect() as connection:
        policy_columns = {
            column["name"] for column in inspect(connection).get_columns("user_policies")
        }
        rider_columns = {
            column["name"] for column in inspect(connection).get_columns("user_policy_riders")
        }
        assert {"source_type", "issuer", "issued_on"} <= policy_columns
        assert {"source_type", "issuer", "issued_on"} <= rider_columns
        policy_source = connection.execute(
            text("SELECT source_type FROM user_policies WHERE policy_id = 'legacy-policy'")
        ).scalar_one()
        rider_source = connection.execute(
            text("SELECT source_type FROM user_policy_riders WHERE rider_id = 'legacy-rider'")
        ).scalar_one()

    assert policy_source == "USER_STATED"
    assert rider_source == "USER_STATED"
    engine.dispose()


def test_user_api_key_migration_upgrades_legacy_token_hash_schema(tmp_path: Path) -> None:
    """The 2026-10-17 per-user key table used token_hash and lacked prefix/lifecycle columns."""
    engine = create_db_engine(f"sqlite:///{tmp_path / 'legacy_keys.db'}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE users ("
                "user_id VARCHAR(64) PRIMARY KEY, "
                "display_alias VARCHAR(100), "
                "birth_year INTEGER, "
                "pin_hash VARCHAR(128), "
                "created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE user_api_keys ("
                "key_id VARCHAR(36) PRIMARY KEY, "
                "user_id VARCHAR(64) NOT NULL, "
                "token_hash VARCHAR(64) NOT NULL UNIQUE, "
                "created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(text("INSERT INTO users (user_id) VALUES ('legacy-key-user')"))
        connection.execute(
            text(
                "INSERT INTO user_api_keys (key_id, user_id, token_hash) "
                "VALUES ('legacy-key', 'legacy-key-user', 'hashed-legacy-token')"
            )
        )

    init_schema(engine)

    with engine.connect() as connection:
        columns = {column["name"] for column in inspect(connection).get_columns("user_api_keys")}
        migrated_hash = connection.execute(
            text("SELECT key_hash FROM user_api_keys WHERE key_id = 'legacy-key'")
        ).scalar_one()

    assert {
        "key_id",
        "user_id",
        "key_hash",
        "key_prefix",
        "note",
        "last_used_at",
        "revoked_at",
    } <= columns
    assert "token_hash" not in columns
    assert migrated_hash == "hashed-legacy-token"

    # New keys must be issuable on the migrated schema.
    repo = PolicyRepository(engine)
    raw_key = "raw-legacy-schema-key"
    repo.create_api_key("legacy-key-user", hash_api_key(raw_key), api_key_prefix(raw_key))
    assert repo.find_active_key_owner(hash_api_key(raw_key)) == "legacy-key-user"
    engine.dispose()