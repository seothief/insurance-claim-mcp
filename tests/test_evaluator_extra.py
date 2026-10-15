"""More evaluation cases: new rule types, custom riders, pending riders and silson generation."""

from claim_service.domain.catalog import STANDARD_RULES
from claim_service.domain.evaluator import evaluate_claim
from claim_service.domain.models import ClaimInput, PolicyOut, RiderOut
from claim_service.domain.silson import resolve_silson_generation

RULES = {rule.rule_id: rule for rule in STANDARD_RULES}


def _rider(
    name: str,
    amount: int,
    rule_id: str | None,
    status: str = "MAPPED",
    custom: dict[str, object] | None = None,
) -> RiderOut:
    return RiderOut(
        rider_id=f"id-{name}",
        rider_name=name,
        coverage_amount=amount,
        mapped_rule_id=rule_id,
        mapping_status=status,  # type: ignore[arg-type]
        custom_rule_config=custom,
    )


def _comprehensive(*riders: RiderOut) -> PolicyOut:
    return PolicyOut(
        policy_id="comp-1",
        company="현대해상",
        product_name="테스트 종합",
        policy_type="COMPREHENSIVE",
        riders=list(riders),
    )


def test_silson_generation_inference_by_enrolled_year() -> None:
    generation, note = resolve_silson_generation(None, 2015)
    assert generation == 2
    assert "2015년" in note
    assert resolve_silson_generation(None, 2023)[0] == 4
    assert resolve_silson_generation(4, 2015)[0] == 4


def test_silson_generation_boundary_year_is_unresolved() -> None:
    generation, note = resolve_silson_generation(None, 2017)
    assert generation is None
    assert "세대가 바뀐 해" in note


def test_silson_generation_missing_both_gives_guidance() -> None:
    generation, note = resolve_silson_generation(None, None)
    assert generation is None
    assert "가입연도가 모두 없어" in note


def test_burn_emergency_and_inpatient_daily() -> None:
    policy = _comprehensive(
        _rider("화상진단비", 100000, "BURN_DIAGNOSIS"),
        _rider("응급실내원비", 50000, "EMERGENCY_ROOM_VISIT"),
        _rider("입원일당", 30000, "INPATIENT_DAILY"),
    )
    claim = ClaimInput(kcd_code="T23.1", is_emergency=True, is_inpatient=True, inpatient_days=3)
    result = evaluate_claim("u", [policy], RULES, claim)
    amounts = {b.rider_name: b.estimated_amount for b in result.matched_benefits}
    assert amounts == {"화상진단비": 100000, "응급실내원비": 50000, "입원일당": 90000}


def test_custom_rider_uses_confirmed_conditions() -> None:
    custom = _rider(
        "무배당 뉴플랜수술담보", 1000000, None, status="CUSTOM",
        custom={"target_keywords": ["수술"]},
    )
    result = evaluate_claim("u", [_comprehensive(custom)], RULES, ClaimInput(treatment_name="수술"))
    assert result.total_estimated_payout == 1000000
    assert "검증되지 않았습니다" in result.matched_benefits[0].basis


def test_needs_clarification_rider_is_pending_not_paid() -> None:
    pending = _rider("무배당 뉴플랜수술담보", 1000000, None, status="NEEDS_CLARIFICATION")
    policy = _comprehensive(pending)
    result = evaluate_claim("u", [policy], RULES, ClaimInput(treatment_name="수술"))
    assert result.matched_benefits == []
    assert result.pending_riders == ["현대해상 / 무배당 뉴플랜수술담보"]


def test_ignored_rider_is_skipped() -> None:
    ignored = _rider("상해사망", 100000, None, status="IGNORED")
    result = evaluate_claim("u", [_comprehensive(ignored)], RULES, ClaimInput(is_injury=True))
    assert result.matched_benefits == []


def test_injury_surgery_requires_injury_flag() -> None:
    policy = _comprehensive(_rider("상해수술비", 1000000, "INJURY_SURGERY"))
    not_injury = evaluate_claim(
        "u", [policy], RULES, ClaimInput(treatment_name="수술", is_injury=False)
    )
    assert not_injury.matched_benefits == []
    injured = evaluate_claim(
        "u", [policy], RULES, ClaimInput(treatment_name="수술", is_injury=True)
    )
    assert injured.total_estimated_payout == 1000000
