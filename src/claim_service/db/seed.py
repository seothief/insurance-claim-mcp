"""Seed standard rules and a synthetic sample user (PII-free) on first run."""

from claim_service.db.repository import PolicyRepository
from claim_service.domain.catalog import STANDARD_RULES
from claim_service.domain.models import PolicyIn, RiderIn, UserIn
from claim_service.service import PolicyService

SAMPLE_USER_ID = "user_123"

SAMPLE_POLICIES: tuple[PolicyIn, ...] = (
    PolicyIn(
        company="삼성화재",
        product_name="무배당 삼성화재 다이렉트 착한실손의료비보장보험(4세대)",
        policy_type="SILSON",
        silson_generation=4,
        enrolled_year=2023,
    ),
    PolicyIn(
        company="현대해상",
        product_name="무배당 퍼펙트플러스종합보험",
        policy_type="COMPREHENSIVE",
        enrolled_year=2021,
        riders=[
            RiderIn(rider_name="골절진단비(치아파열제외)", coverage_amount=300000),
            RiderIn(rider_name="깁스치료비", coverage_amount=500000),
            RiderIn(rider_name="질병수술비", coverage_amount=500000),
            RiderIn(rider_name="상해수술비", coverage_amount=1000000),
            RiderIn(rider_name="독감(인플루엔자)치료비", coverage_amount=200000),
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
