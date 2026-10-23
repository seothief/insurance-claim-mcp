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

# KCD (한국표준질병·사인분류) 공식 코드 마스터.
# 통계청 표준분류/KOICD 또는 HIRA 상병마스터 원본에서 적재한다. 계산의 "공통 언어"로만 쓰이고,
# 어떤 특약이 어떤 코드 범위를 보장하는지는 개별 약관(coverage_rules/user_policy_riders)이 결정한다.
kcd_codes = Table(
    "kcd_codes",
    metadata,
    Column("code", String(10), primary_key=True),
    Column("category", String(1), nullable=False),  # 대분류 A~Z (예: S=손상, T=외인)
    Column("level", Integer, nullable=False),       # 1=대분류 2=중 3=소 4=세 5=세세
    Column("ko_name", String(500), nullable=False),
    Column("en_name", String(500), nullable=True),
    Column("source_version", String(20), nullable=False),  # 예: KCD-8, KCD-9
    Column("verified", Boolean, nullable=False, default=True),  # 공식 출처 코드는 True
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

user_api_keys = Table(
    "user_api_keys",
    metadata,
    Column("key_id", String(36), primary_key=True),
    Column(
        "user_id",
        String(64),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    # Only the SHA-256 hash of the key is stored. The raw key is shown once at issue time.
    Column("key_hash", String(64), nullable=False, unique=True),
    # Short display prefix (first 8 chars) for logs and key lists without exposing the secret.
    Column("key_prefix", String(16), nullable=False),
    Column("note", String(200), nullable=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("last_used_at", DateTime(timezone=True), nullable=True),
    Column("revoked_at", DateTime(timezone=True), nullable=True),
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
    Column("source_type", String(32), nullable=False, default="USER_STATED"),
    Column("issuer", String(100), nullable=True),
    Column("issued_on", String(10), nullable=True),
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
    # Source of the rider data. Only POLICY_CERTIFICATE may be calculated; existing rows are
    # migrated to USER_STATED. Issuer and date are kept; no policy number or personal data.
    Column("source_type", String(32), nullable=False, default="USER_STATED"),
    Column("issuer", String(100), nullable=True),
    Column("issued_on", String(10), nullable=True),
    UniqueConstraint("policy_id", "rider_name", name="uq_policy_rider_name"),
)

