"""Onboarding guidance: next-step messages, AI follow-up prompts and the registration guide."""

from collections.abc import Iterable, Sequence

from claim_service.domain.models import CoverageRule, OnboardingStatus, UnresolvedRider

RESOLVE_OPTIONS: dict[str, str] = {
    "MAPPED": "표준 담보 규칙 하나를 골라 연결 (mapped_rule_id)",
    "CUSTOM": "표준 규칙이 없을 때 증권 조건으로 직접 정의 (custom_rule_config)",
    "IGNORED": "사망·후유장해 등 영수증 청구와 무관한 담보 (계산에서 제외)",
}


def next_step_message(status: OnboardingStatus, unresolved_count: int) -> str:
    if status == "CREATED":
        return "보험증권 또는 보험사 앱 조회 화면으로 보험을 등록해 주세요 (register_user_policy)."
    if status == "NEEDS_CLARIFICATION":
        return (
            f"확인이 필요한 특약이 {unresolved_count}개 있습니다. "
            "증권을 다시 확인해 resolve_user_rider로 확정해 주세요."
        )
    return "등록이 완료되어 청구 예상액을 계산할 수 있습니다 (evaluate_claim)."


def build_follow_up_prompt(company: str, unresolved: Sequence[UnresolvedRider]) -> str:
    """Instruction for the registering AI when some riders could not be mapped automatically."""
    lines = [
        f"[{company}] 아래 특약은 표준 규칙에 자동 매핑되지 않았습니다. "
        "증권 원문을 다시 확인하거나 사용자에게 물은 뒤 resolve_user_rider를 호출하세요.",
    ]
    for rider in unresolved:
        candidates = ", ".join(rider.candidate_rules) or "없음 (커스텀 정의 또는 IGNORED)"
        lines.append(
            f"- rider_id={rider.rider_id} / 특약명='{rider.rider_name}' / 후보 규칙: {candidates}"
        )
    lines.append(
        "mapping_status는 MAPPED(규칙 연결), CUSTOM(증권 조건으로 정의), "
        "IGNORED(청구 대상 아님) 중 하나로 확정하세요. 확실하지 않으면 사용자에게 확인하세요."
    )
    return "\n".join(lines)


def build_onboarding_guide(rules: Iterable[CoverageRule]) -> dict[str, object]:
    """Static guide that tells the registering AI how to collect and submit policy data."""
    return {
        "steps": [
            "1. register_user로 사용자를 먼저 가입시킵니다 (user_id는 영문/숫자/_/- 만 사용).",
            "2. 보험증권 PDF, 보험사 앱 캡처, 통합 조회 화면에서 보험사, 상품명, 특약명, "
            "가입금액을 읽습니다. 실손은 세대 또는 가입연도를 함께 확인합니다.",
            "3. register_user_policy로 보험별로 등록합니다. 같은 보험을 다시 등록하면 갱신됩니다 "
            "(보험사+상품명 기준).",
            "4. 응답의 unresolved_riders와 ai_follow_up_prompt를 확인해 resolve_user_rider로 "
            "특약을 확정합니다.",
            "5. get_user_profile로 onboarding_status가 READY인지 확인합니다.",
        ],
        "supported_rules": [
            {
                "rule_id": rule.rule_id,
                "display_name": rule.display_name,
                "match_keywords": rule.match_keywords,
                "verified": rule.verified,
            }
            for rule in rules
        ],
        "resolve_options": RESOLVE_OPTIONS,
        "example_registration": {
            "company": "현대해상",
            "product_name": "무배당 퍼펙트플러스종합보험",
            "policy_type": "COMPREHENSIVE",
            "enrolled_year": 2021,
            "riders": [
                {"rider_name": "골절진단비(치아파열제외)", "coverage_amount": 300000},
                {"rider_name": "무배당 뉴플랜수술담보", "coverage_amount": 1000000},
            ],
        },
        "notes": [
            "특약 금액은 원 단위 정수로 입력합니다.",
            "실손 세대를 모르면 생략해도 되지만, 가입연도도 없으면 계산되지 않습니다.",
            "모든 약관 수치는 verified=false입니다. 예상치로만 안내하세요.",
        ],
    }
