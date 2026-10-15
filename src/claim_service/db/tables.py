"""SQLAlchemy Core table definitions. Works with SQLite (local) and PostgreSQL (cloud)."""

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)

metadata = MetaData()

coverage_rules = Table(
    "coverage_rules",
    metadata,
    Column("rule_id", String(64), primary_key=True),
    Column("category", String(32), nullable=False),
    Column("display_name", String(200), nullable=False),
    Column("match_keywords", JSON, nullable=False),
    Column("rule_config", JSON, nullable=False),
    Column("required_documents", JSON, nullable=False),
    Column("verified", Boolean, nullable=False, default=False),
    Column("source_reference", Text, nullable=False),
)

users = Table(
    "users",
    metadata,
    Column("user_id", String(64), primary_key=True),
    Column("display_alias", String(100), nullable=True),
    Column("birth_year", Integer, nullable=True),
    Column("pin_hash", String(128), nullable=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

user_policies = Table(
    "user_policies",
    metadata,
    Column("policy_id", String(36), primary_key=True),
    Column(
        "user_id",
        String(64),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("company", String(100), nullable=False),
    Column("product_name", String(200), nullable=False),
    Column("policy_type", String(32), nullable=False),
    Column("silson_generation", Integer, nullable=True),
    Column("enrolled_year", Integer, nullable=True),
    Column("is_active", Boolean, nullable=False, default=True),
    UniqueConstraint("user_id", "company", "product_name", name="uq_user_policy_identity"),
)

user_policy_riders = Table(
    "user_policy_riders",
    metadata,
    Column("rider_id", String(36), primary_key=True),
    Column(
        "policy_id",
        String(36),
        ForeignKey("user_policies.policy_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("rider_name", String(200), nullable=False),
    Column(
        "mapped_rule_id",
        String(64),
        ForeignKey("coverage_rules.rule_id"),
        nullable=True,
    ),
    Column("coverage_amount", Integer, nullable=False),
    Column("mapping_status", String(32), nullable=False, default="MAPPED"),
    Column("custom_rule_config", JSON, nullable=True),
    UniqueConstraint("policy_id", "rider_name", name="uq_policy_rider_name"),
)

