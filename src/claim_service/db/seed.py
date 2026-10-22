"""Seed standard coverage rules on first run."""

from claim_service.db.repository import PolicyRepository
from claim_service.domain.catalog import STANDARD_RULES


def seed_standard_rules(repo: PolicyRepository) -> None:
    repo.upsert_rules(STANDARD_RULES)
