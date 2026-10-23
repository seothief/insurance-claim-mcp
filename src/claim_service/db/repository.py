"""Repository for users, policies, riders and standard coverage rules (SQLAlchemy Core).

Methods do no business validation beyond ownership checks. Business rules live in the service.
"""

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import Connection, Engine, RowMapping, delete, func, insert, select, update

from claim_service.db.tables import (
    coverage_rules,
    user_api_keys,
    user_policies,
    user_policy_riders,
    users,
)
from claim_service.domain.errors import DuplicateRiderError, NotFoundError
from claim_service.domain.models import CoverageRule, MappingStatus, PolicyOut, RiderOut, UserIn


@dataclass(frozen=True)
class RiderPlan:
    """One incoming rider ready to be written.

    `explicit_mapping` is False when the caller only supplied a name and amount, so an existing
    confirmed mapping is kept on update.
    """

    rider_name: str
    coverage_amount: int
    mapped_rule_id: str | None
    mapping_status: MappingStatus
    custom_rule_config: dict[str, Any] | None
    explicit_mapping: bool
    source_type: str = "USER_STATED"
    issuer: str | None = None
    issued_on: str | None = None


class PolicyRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    # ---- standard rules -------------------------------------------------
    def upsert_rules(self, rules: Iterable[CoverageRule]) -> None:
        with self._engine.begin() as conn:
            for rule in rules:
                values: dict[str, Any] = {
                    "category": rule.category,
                    "display_name": rule.display_name,
                    "match_keywords": rule.match_keywords,
                    "rule_config": rule.rule_config,
                    "required_documents": rule.required_documents,
                    "verified": rule.verified,
                    "source_reference": rule.source_reference,
                }
                exists = conn.execute(
                    select(coverage_rules.c.rule_id).where(
                        coverage_rules.c.rule_id == rule.rule_id
                    )
                ).first()
                if exists is None:
                    conn.execute(insert(coverage_rules).values(rule_id=rule.rule_id, **values))
                else:
                    conn.execute(
                        update(coverage_rules)
                        .where(coverage_rules.c.rule_id == rule.rule_id)
                        .values(**values)
                    )

    def get_rules(self) -> dict[str, CoverageRule]:
        with self._engine.connect() as conn:
            rows = conn.execute(select(coverage_rules)).mappings().all()
        return {
            row["rule_id"]: CoverageRule(
                rule_id=row["rule_id"],
                category=row["category"],
                display_name=row["display_name"],
                match_keywords=row["match_keywords"],
                rule_config=row["rule_config"],
                required_documents=row["required_documents"],
                verified=row["verified"],
                source_reference=row["source_reference"],
            )
            for row in rows
        }

    # ---- users ----------------------------------------------------------
    def create_user(self, user: UserIn, pin_hash: str | None = None) -> bool:
        """Insert a user. Returns False when the user already exists."""
        with self._engine.begin() as conn:
            exists = conn.execute(
                select(users.c.user_id).where(users.c.user_id == user.user_id)
            ).first()
            if exists is not None:
                return False
            conn.execute(
                insert(users).values(
                    user_id=user.user_id,
                    display_alias=user.display_alias,
                    birth_year=user.birth_year,
                    pin_hash=pin_hash,
                )
            )
            return True

    def set_user_pin_hash(self, user_id: str, pin_hash: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                update(users).where(users.c.user_id == user_id).values(pin_hash=pin_hash)
            )

    def ensure_user(self, user_id: str, pin_hash: str | None = None) -> None:
        """Create a bare user record if needed (used when a policy is registered first)."""
        with self._engine.begin() as conn:
            exists = conn.execute(
                select(users.c.user_id).where(users.c.user_id == user_id)
            ).first()
            if exists is None:
                conn.execute(insert(users).values(user_id=user_id, pin_hash=pin_hash))

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        with self._engine.connect() as conn:
            row = conn.execute(select(users).where(users.c.user_id == user_id)).mappings().first()
        return None if row is None else dict(row)

    def user_exists(self, user_id: str) -> bool:
        return self.get_user(user_id) is not None

    # ---- per-user API keys ---------------------------------------------
    def create_api_key(self, user_id: str, key_hash: str, key_prefix: str) -> str:
        """Store a new per-user API key hash and return its key_id."""
        if not self.user_exists(user_id):
            raise NotFoundError(f"사용자를 찾을 수 없습니다: {user_id}")
        key_id = str(uuid.uuid4())
        with self._engine.begin() as conn:
            conn.execute(
                insert(user_api_keys).values(
                    key_id=key_id,
                    user_id=user_id,
                    key_hash=key_hash,
                    key_prefix=key_prefix,
                )
            )
        return key_id

    def find_active_key_owner(self, key_hash: str) -> str | None:
        """Return the user_id owning an active API key with this hash, or None."""
        with self._engine.connect() as conn:
            row = conn.execute(
                select(user_api_keys.c.user_id)
                .where(user_api_keys.c.key_hash == key_hash)
                .where(user_api_keys.c.revoked_at.is_(None))
            ).mappings().first()
        return None if row is None else str(row["user_id"])

    def list_api_keys(self, user_id: str) -> list[dict[str, Any]]:
        """Return the user's API key rows (never the hash or the raw key)."""
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(
                    user_api_keys.c.key_id,
                    user_api_keys.c.key_prefix,
                    user_api_keys.c.revoked_at,
                )
                .where(user_api_keys.c.user_id == user_id)
                .order_by(user_api_keys.c.created_at)
            ).mappings().all()
        return [dict(row) for row in rows]

    def revoke_api_key(self, user_id: str, key_id: str) -> bool:
        """Mark a key as revoked. Returns False when the key does not exist or has no owner."""
        with self._engine.begin() as conn:
            result = conn.execute(
                update(user_api_keys)
                .where(user_api_keys.c.key_id == key_id)
                .where(user_api_keys.c.user_id == user_id)
                .values(revoked_at=func.now())
            )
            return result.rowcount > 0

    # ---- policies -------------------------------------------------------
    def list_policies(self, user_id: str) -> list[PolicyOut]:
        with self._engine.connect() as conn:
            rows = (
                conn.execute(
                    select(user_policies)
                    .where(user_policies.c.user_id == user_id)
                    .where(user_policies.c.is_active.is_(True))
                    .order_by(user_policies.c.company, user_policies.c.product_name)
                )
                .mappings()
                .all()
            )
            return [self._to_policy(conn, row) for row in rows]

    def delete_policy(self, user_id: str, policy_id: str) -> bool:
        with self._engine.begin() as conn:
            result = conn.execute(
                delete(user_policies)
                .where(user_policies.c.policy_id == policy_id)
                .where(user_policies.c.user_id == user_id)
            )
            return result.rowcount > 0

    def save_policy(
        self,
        user_id: str,
        policy: PolicyOut,
        incoming_riders: Sequence[RiderPlan],
        replace_riders: bool,
    ) -> tuple[Literal["CREATED", "UPDATED"], PolicyOut]:
        """Insert a new policy or update the existing one with the same company and product name.

        Returns ("CREATED" | "UPDATED", stored policy). Existing rider mappings that the user or AI
        already confirmed are kept when the incoming rider has no explicit mapping.
        """
        with self._engine.begin() as conn:
            existing = conn.execute(
                select(user_policies.c.policy_id)
                .where(user_policies.c.user_id == user_id)
                .where(user_policies.c.company == policy.company)
                .where(user_policies.c.product_name == policy.product_name)
            ).first()
            action: Literal["CREATED", "UPDATED"]
            if existing is None:
                action = "CREATED"
                policy_id = str(uuid.uuid4())
                conn.execute(
                    insert(user_policies).values(
                        policy_id=policy_id,
                        user_id=user_id,
                        company=policy.company,
                        product_name=policy.product_name,
                        policy_type=policy.policy_type,
                        silson_generation=policy.silson_generation,
                        enrolled_year=policy.enrolled_year,
                        source_type=policy.source_type,
                        issuer=policy.issuer,
                        issued_on=policy.issued_on,
                        is_active=True,
                    )
                )
            else:
                action = "UPDATED"
                policy_id = str(existing[0])
                conn.execute(
                    update(user_policies)
                    .where(user_policies.c.policy_id == policy_id)
                    .values(
                        policy_type=policy.policy_type,
                        silson_generation=policy.silson_generation,
                        enrolled_year=policy.enrolled_year,
                        source_type=policy.source_type,
                        issuer=policy.issuer,
                        issued_on=policy.issued_on,
                        is_active=True,
                    )
                )
                if replace_riders:
                    conn.execute(
                        delete(user_policy_riders).where(
                            user_policy_riders.c.policy_id == policy_id
                        )
                    )
            self._merge_riders(conn, policy_id, incoming_riders)
            stored = self._read_policy(conn, user_id, policy_id)
        if stored is None:  # pragma: no cover - the row was written in this transaction
            raise RuntimeError("policy was saved but could not be read back")
        return action, stored

    @staticmethod
    def _merge_riders(conn: Connection, policy_id: str, incoming: Sequence[RiderPlan]) -> None:
        names = [rider.rider_name for rider in incoming]
        duplicated = sorted({name for name in names if names.count(name) > 1})
        if duplicated:
            raise DuplicateRiderError(f"같은 보험에 중복된 특약명이 있습니다: {duplicated}")
        existing = {
            row["rider_name"]: row
            for row in conn.execute(
                select(user_policy_riders).where(user_policy_riders.c.policy_id == policy_id)
            ).mappings()
        }
        for rider in incoming:
            current = existing.get(rider.rider_name)
            if current is None:
                conn.execute(
                    insert(user_policy_riders).values(
                        rider_id=str(uuid.uuid4()),
                        policy_id=policy_id,
                        rider_name=rider.rider_name,
                        mapped_rule_id=rider.mapped_rule_id,
                        mapping_status=rider.mapping_status,
                        custom_rule_config=rider.custom_rule_config,
                        coverage_amount=rider.coverage_amount,
                        source_type=rider.source_type,
                        issuer=rider.issuer,
                        issued_on=rider.issued_on,
                    )
                )
                continue
            # The source describes the latest document, so it is refreshed on every registration.
            values: dict[str, Any] = {
                "coverage_amount": rider.coverage_amount,
                "source_type": rider.source_type,
                "issuer": rider.issuer,
                "issued_on": rider.issued_on,
            }
            # Overwrite the mapping only when it is unresolved or the caller set it explicitly.
            # A confirmed mapping (MAPPED / CUSTOM / IGNORED) is kept on re-registration.
            unresolved = current["mapping_status"] == "NEEDS_CLARIFICATION"
            if rider.explicit_mapping or unresolved:
                values.update(
                    mapped_rule_id=rider.mapped_rule_id,
                    mapping_status=rider.mapping_status,
                    custom_rule_config=rider.custom_rule_config,
                )
            conn.execute(
                update(user_policy_riders)
                .where(user_policy_riders.c.rider_id == current["rider_id"])
                .values(**values)
            )

    def get_rider(self, user_id: str, rider_id: str) -> RiderOut | None:
        """Return a rider only when it belongs to one of the user's policies."""
        with self._engine.connect() as conn:
            row = (
                conn.execute(
                    select(user_policy_riders)
                    .join(
                        user_policies,
                        user_policies.c.policy_id == user_policy_riders.c.policy_id,
                    )
                    .where(user_policy_riders.c.rider_id == rider_id)
                    .where(user_policies.c.user_id == user_id)
                )
                .mappings()
                .first()
            )
            return None if row is None else self._to_rider(row)

    def update_rider(self, user_id: str, rider_id: str, values: dict[str, Any]) -> bool:
        """Update rider columns only when the rider belongs to the user."""
        with self._engine.begin() as conn:
            owned = conn.execute(
                select(user_policy_riders.c.rider_id)
                .join(
                    user_policies,
                    user_policies.c.policy_id == user_policy_riders.c.policy_id,
                )
                .where(user_policy_riders.c.rider_id == rider_id)
                .where(user_policies.c.user_id == user_id)
            ).first()
            if owned is None:
                return False
            if values:
                conn.execute(
                    update(user_policy_riders)
                    .where(user_policy_riders.c.rider_id == rider_id)
                    .values(**values)
                )
            return True

    # ---- helpers --------------------------------------------------------
    def _read_policy(self, conn: Connection, user_id: str, policy_id: str) -> PolicyOut | None:
        row = (
            conn.execute(
                select(user_policies)
                .where(user_policies.c.policy_id == policy_id)
                .where(user_policies.c.user_id == user_id)
            )
            .mappings()
            .first()
        )
        return None if row is None else self._to_policy(conn, row)

    @staticmethod
    def _to_rider(row: RowMapping) -> RiderOut:
        return RiderOut(
            rider_id=row["rider_id"],
            rider_name=row["rider_name"],
            coverage_amount=row["coverage_amount"],
            mapped_rule_id=row["mapped_rule_id"],
            mapping_status=row["mapping_status"],
            custom_rule_config=row["custom_rule_config"],
            source_type=row["source_type"] or "USER_STATED",
            issuer=row["issuer"],
            issued_on=row["issued_on"],
        )

    @staticmethod
    def _to_policy(conn: Connection, row: RowMapping) -> PolicyOut:
        rider_rows = (
            conn.execute(
                select(user_policy_riders)
                .where(user_policy_riders.c.policy_id == row["policy_id"])
                .order_by(user_policy_riders.c.rider_name)
            )
            .mappings()
            .all()
        )
        return PolicyOut(
            policy_id=row["policy_id"],
            company=row["company"],
            product_name=row["product_name"],
            policy_type=row["policy_type"],
            silson_generation=row["silson_generation"],
            enrolled_year=row["enrolled_year"],
            source_type=row["source_type"] or "USER_STATED",
            issuer=row["issuer"],
            issued_on=row["issued_on"],
            riders=[PolicyRepository._to_rider(r) for r in rider_rows],
        )
