"""Seed standard rules and a synthetic sample user (PII-free) on first run."""

from claim_service.db.repository import PolicyRepository
from claim_service.domain.catalog import STANDARD_RULES
from claim_service.domain.models import PolicyIn, RiderIn, UserIn
from claim_service.service import PolicyService

SAMPLE_USER_ID = "user_123"

# Synthetic sample data. It is not a real policy, so it is marked SYNTHETIC_SAMPLE and is never
# calculated (only a POLICY_CERTIFICATE source may be calculated).
SAMPLE_POLICIES: tuple[PolicyIn, ...] = (
    PolicyIn(
        company="샘플보험사A",
        product_name="샘플 실손의료비보험(4세대)",
        policy_type="SILSON",
        silson_generation=4,
        enrolled_year=2023,
        source_type="SYNTHETIC_SAMPLE",
    ),
    PolicyIn(
        company="샘플보험사B",
        product_name="샘플 종합보험",
        policy_type="COMPREHENSIVE",
        enrolled_year=2021,
        source_type="SYNTHETIC_SAMPLE",
        riders=[
            RiderIn(
                rider_name="골절진단비(샘플)",
                coverage_amount=300000,
                source_type="SYNTHETIC_SAMPLE",
            ),
            RiderIn(
                rider_name="깁스치료비(샘플)",
                coverage_amount=500000,
                source_type="SYNTHETIC_SAMPLE",
            ),
        ],
    ),
)


def seed_standard_rules(repo: PolicyRepository) -> None:
    repo.upsert_rules(STANDARD_RULES)


def seed_sample_user(repo: PolicyRepository, service: PolicyService) -> None:
    """Register the synthetic sample user once. Existing data is left untouched."""
    if repo.user_exists(SAMPLE_USER_ID):
        return
    service.register_user(UserIn(user_id=SAMPLE_USER_ID, display_alias="샘플 사용자"))
    for policy in SAMPLE_POLICIES:
        service.register_policy(SAMPLE_USER_ID, policy)


def seed_all(repo: PolicyRepository, service: PolicyService) -> None:
    seed_standard_rules(repo)
    seed_sample_user(repo, service)
