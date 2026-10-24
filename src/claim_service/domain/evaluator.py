"""Claim evaluation: match a user's policies against standard rules and estimate payouts.

No I/O happens here. Results are informational estimates, not payment decisions.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from claim_service.domain.models import (
    ClaimEvaluation,
    ClaimInput,
    CoverageRule,
    PolicyOut,
    RiderOut,
)
from claim_service.domain.outcome import Outcome, make_outcome
from claim_service.domain.rider_rules import evaluate_rider

DISCLAIMER = (
    "본 결과는 참고 정보이며 보험금 지급을 확정하지 않습니다. "
    "약관 원문으로 검증되지 않은 규칙이나 확인되지 않은 진료 사실은 계산하지 않았습니다."
)
BASE_DOCUMENTS: tuple[str, ...] = (
    "진료비 계산서·영수증 (병원 원무과 발급)",
    "진료비 세부내역서 (급여/비급여 분리)",
)


def evaluate_claim(
    user_id: str,
    policies: Sequence[PolicyOut],
    rules: Mapping[str, CoverageRule],
    claim: ClaimInput,
) -> ClaimEvaluation:
    outcomes: list[Outcome] = []
    pending: list[str] = []
    unverified: list[str] = []
    for policy in policies:
        if policy.policy_type == "SILSON":
            if not policy.is_source_verified:
                # Strict rule: the generation and deductibles come only from a policy certificate.
                unverified.append(f"{policy.company} / {policy.product_name}")
                continue
            silson = _evaluate_silson(policy, rules, claim)
            if silson is not None:
                outcomes.append(silson)
            continue
        for rider in policy.riders:
            if rider.mapping_status == "NEEDS_CLARIFICATION":
                pending.append(f"{policy.company} / {rider.rider_name}")
                continue
            if not policy.is_source_verified or (
                not rider.is_source_verified and rider.mapping_status != "IGNORED"
            ):
                # Strict rule: a rider without a policy-certificate source is never calculated.
                unverified.append(f"{policy.company} / {rider.rider_name}")
                continue
            outcome = _evaluate_rider(policy, rider, rules, claim)
            if outcome is not None:
                outcomes.append(outcome)

    documents = list(BASE_DOCUMENTS)
    for outcome in outcomes:
        if outcome.result.status != "ELIGIBLE" or outcome.rule_id is None:
            continue
        if outcome.rule_id not in rules:
            continue
        for doc in rules[outcome.rule_id].required_documents:
            if doc not in documents:
                documents.append(doc)

    total = sum(o.result.estimated_amount for o in outcomes if o.result.status == "ELIGIBLE")
    return ClaimEvaluation(
        user_id=user_id,
        matched_benefits=[o.result for o in outcomes],
        total_estimated_payout=total,
        required_documents=documents,
        pending_riders=pending,
        unverified_source_riders=unverified,
        disclaimer=DISCLAIMER,
    )


def _evaluate_rider(
    policy: PolicyOut,
    rider: RiderOut,
    rules: Mapping[str, CoverageRule],
    claim: ClaimInput,
) -> Outcome | None:
    if rider.mapping_status == "IGNORED":
        return None
    if rider.mapping_status == "CUSTOM":
        return make_outcome(
            policy,
            rider.rider_name,
            None,
            "NOT_EVALUATED",
            0,
            "커스텀 조건이 약관 원문으로 검증되지 않아 계산하지 않았습니다.",
        )
    if rider.mapped_rule_id is None or rider.mapped_rule_id not in rules:
        return None
    rule = rules[rider.mapped_rule_id]
    # 특약별 지급 요건(증권 근거)이 있으면 표준 규칙의 rule_config를 대체해 계산에 쓴다.
    # 이때 검증 상태는 증권 근거로 간주한다(Fail-Closed 예외는 개인 특약 source 검증이 담당).
    override_used = rider.rule_config_override is not None and rider.is_source_verified
    if override_used:
        rule = rule.model_copy(
            update={
                "rule_config": rider.rule_config_override,
                "verified": True,
                "source_reference": "특약 증권/약관에서 확인한 지급 요건 (rider override)",
            }
        )
    if not rule.verified:
        return make_outcome(
            policy,
            rider.rider_name,
            rule.rule_id,
            "NOT_EVALUATED",
            0,
            f"'{rule.display_name}' 규칙이 약관 원문으로 검증되지 않아 계산하지 않았습니다.",
        )
    outcome = evaluate_rider(rule, policy, rider, claim)
    if outcome is not None and override_used:
        outcome = Outcome(
            result=outcome.result.model_copy(
                update={
                    "basis": outcome.result.basis
                    + " (이 특약의 증권/약관에서 확인한 지급 요건 기준)"
                }
            ),
            rule_id=outcome.rule_id,
        )
    return outcome


def _evaluate_silson(
    policy: PolicyOut, rules: Mapping[str, CoverageRule], claim: ClaimInput
) -> Outcome | None:
    total_cost = claim.cost_covered + claim.cost_uncovered
    if total_cost <= 0:
        return None

    label = (
        "입원" if claim.is_inpatient is True
        else "통원" if claim.is_inpatient is False
        else "진료 유형 미확인"
    )
    name = f"{policy.product_name}({label})"
    if policy.silson_generation is None:
        return make_outcome(
            policy, name, None, "NOT_EVALUATED", 0,
            "실손보험 세대가 지정되지 않아 계산하지 않았습니다. 증권에서 세대를 확인해 주세요.",
        )
    rule_id = f"SILSON_GEN{policy.silson_generation}"
    rule = rules.get(rule_id)
    if rule is None or not rule.verified or not rule.rule_config:
        return make_outcome(
            policy, name, rule_id, "NOT_EVALUATED", 0,
            f"{policy.silson_generation}세대 실손 규칙의 약관 검증 또는 수치 입력이 완료되지 않아 "
            "계산하지 않았습니다.",
        )

    if claim.is_inpatient is None:
        return make_outcome(
            policy,
            name,
            rule_id,
            "NOT_EVALUATED",
            0,
            "입원/통원 여부가 확인되지 않아 실손 계산을 보류했습니다.",
        )

    cfg: dict[str, Any] = rule.rule_config
    if claim.is_inpatient:
        covered_ratio = float(cfg["inpatient_covered_ratio"])
        uncovered_ratio = float(cfg["inpatient_uncovered_ratio"])
        covered_pay = int(claim.cost_covered * covered_ratio)
        uncovered_pay = int(claim.cost_uncovered * uncovered_ratio)
        basis = (
            f"입원 의료비 {total_cost:,}원에 대해 급여 {covered_ratio:.0%}, "
            f"비급여 {uncovered_ratio:.0%} 보장 기준 적용 (약관 대조 전 예상치)"
        )
    else:
        if claim.hospital_type is None:
            return make_outcome(
                policy,
                name,
                rule_id,
                "NOT_EVALUATED",
                0,
                "통원 의료기관 유형이 확인되지 않아 실손 계산을 보류했습니다.",
            )
        min_deductible = int(cfg["outpatient_deductible"][claim.hospital_type])
        covered_deductible = max(
            min_deductible,
            int(claim.cost_covered * float(cfg["outpatient_covered_deductible_ratio"])),
        )
        covered_pay = max(0, claim.cost_covered - covered_deductible)

        uncovered_deductible = 0
        uncovered_pay = 0
        if claim.cost_uncovered > 0:
            uncovered_deductible = max(
                int(cfg["outpatient_uncovered_deductible_min"]),
                int(claim.cost_uncovered * float(cfg["outpatient_uncovered_deductible_ratio"])),
            )
            uncovered_pay = max(0, claim.cost_uncovered - uncovered_deductible)
        basis = (
            f"총 진료비 {total_cost:,}원 중 급여 공제 {covered_deductible:,}원, "
            f"비급여 공제 {uncovered_deductible:,}원을 차감한 예상 수령액입니다 "
            "(약관 대조 전 예상치)."
        )

    return make_outcome(
        policy, name, rule_id, "ELIGIBLE", covered_pay + uncovered_pay, basis
    )
