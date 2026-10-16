"""Tests for additive database migrations on existing local schemas."""

from pathlib import Path

from sqlalchemy import inspect, text

from claim_service.db.engine import create_db_engine, init_schema
from claim_service.db.tables import metadata


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