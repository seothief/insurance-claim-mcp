"""Unit tests for the pure evaluation engine (no database)."""

from claim_service.domain.catalog import STANDARD_RULES, candidate_rule_ids, match_fixed_rule
from claim_service.domain.evaluator import evaluate_claim
from claim_service.domain.models import ClaimInput, PolicyOut, RiderOut

RULES = {rule.rule_id: rule.model_copy(update={"verified": True}) for rule in STANDARD_RULES}
UNVERIFIED_RULES = {rule.rule_id: rule for rule in STANDARD_RULES}


def _rider(
    name: str,
    amount: int,
    rule_id: str | None,
    status: str = "MAPPED",
    custom: dict[str, object] | None = None,
) -> RiderOut:
    # These fixtures model a policy certificate, the only source the engine calculates from.
    return RiderOut(
        rider_id=f"id-{name}",
        rider_name=name,
        coverage_amount=amount,
        mapped_rule_id=rule_id,
        mapping_status=status,  # type: ignore[arg-type]
        custom_rule_config=custom,
        source_type="POLICY_CERTIFICATE",
    )


def _silson(generation: int | None = 4) -> PolicyOut:
    return PolicyOut(
        policy_id="silson-1",
        company="삼성화재",
        product_name="테스트 실손",
        policy_type="SILSON",
        silson_generation=generation,
        riders=[],
        source_type="POLICY_CERTIFICATE",
    )


def _comprehensive(*riders: RiderOut) -> PolicyOut:
    return PolicyOut(
        policy_id="comp-1",
        company="현대해상",
        product_name="테스트 종합",
        policy_type="COMPREHENSIVE",
        riders=list(riders),
        source_type="POLICY_CERTIFICATE",
    )


def test_match_fixed_rule_maps_known_riders() -> None:
    assert match_fixed_rule("골절진단비(치아파열제외)", RULES.values()) == "FRACTURE_DIAGNOSIS"
    assert match_fixed_rule("깁스치료비", RULES.values()) == "CAST_TREATMENT"
    assert match_fixed_rule("독감(인플루엔자)치료비", RULES.values()) == "FLU_ANTIVIRAL"
    assert match_fixed_rule("화상진단비", RULES.values()) == "BURN_DIAGNOSIS"
    assert match_fixed_rule("무배당 뉴플랜수술담보", RULES.values()) is None


def test_candidate_rules_suggest_similar_riders() -> None:
    assert "DISEASE_SURGERY" in candidate_rule_ids("무배당 질병수술담보", RULES.values())


def test_silson_outpatient_clinic_deductions() -> None:
    claim = ClaimInput(
        cost_covered=25000,
        cost_uncovered=60000,
        hospital_type="clinic",
        is_inpatient=False,
    )
    result = evaluate_claim("u", [_silson()], RULES, claim)
    benefit = result.matched_benefits[0]
    # covered: max(10000, 25000*0.2=5000)=10000 deducted -> 15000
    # uncovered: max(30000, 60000*0.3=18000)=30000 deducted -> 30000
    assert benefit.status == "ELIGIBLE"
    assert benefit.estimated_amount == 45000
    assert result.total_estimated_payout == 45000


def test_silson_inpatient_ratio() -> None:
    claim = ClaimInput(cost_covered=100000, cost_uncovered=100000, is_inpatient=True)
    result = evaluate_claim("u", [_silson()], RULES, claim)
    assert result.matched_benefits[0].estimated_amount == 80000 + 70000


def test_silson_missing_visit_type_or_hospital_type_is_not_evaluated() -> None:
    policy = _silson()
    missing_visit_type = evaluate_claim(
        "u", [policy], RULES, ClaimInput(cost_covered=10000)
    )
    assert missing_visit_type.matched_benefits[0].status == "NOT_EVALUATED"
    missing_hospital_type = evaluate_claim(
        "u", [policy], RULES, ClaimInput(cost_covered=10000, is_inpatient=False)
    )
    assert missing_hospital_type.matched_benefits[0].status == "NOT_EVALUATED"


def test_silson_without_generation_is_not_evaluated() -> None:
    result = evaluate_claim("u", [_silson(generation=None)], RULES, ClaimInput(cost_covered=10000))
    benefit = result.matched_benefits[0]
    assert benefit.status == "NOT_EVALUATED"
    assert "세대가 지정되지 않아" in benefit.basis
    assert result.total_estimated_payout == 0


def test_silson_generation_without_numbers_is_not_evaluated() -> None:
    result = evaluate_claim("u", [_silson(generation=2)], RULES, ClaimInput(cost_covered=10000))
    assert result.matched_benefits[0].status == "NOT_EVALUATED"
    assert result.total_estimated_payout == 0


def test_fracture_eligible_and_excluded() -> None:
    policy = _comprehensive(_rider("골절진단비", 300000, "FRACTURE_DIAGNOSIS"))
    eligible = evaluate_claim("u", [policy], RULES, ClaimInput(kcd_code="S82.1"))
    assert eligible.total_estimated_payout == 300000
    excluded = evaluate_claim("u", [policy], RULES, ClaimInput(kcd_code="S02.5"))
    assert excluded.matched_benefits[0].status == "EXCLUDED"
    assert excluded.total_estimated_payout == 0


def test_unverified_standard_rule_is_not_evaluated() -> None:
    policy = _comprehensive(_rider("골절진단비", 300000, "FRACTURE_DIAGNOSIS"))
    result = evaluate_claim("u", [policy], UNVERIFIED_RULES, ClaimInput(kcd_code="S82.1"))
    assert result.matched_benefits[0].status == "NOT_EVALUATED"
    assert result.matched_benefits[0].estimated_amount == 0
    assert result.total_estimated_payout == 0


def test_missing_diagnosis_fact_is_not_evaluated() -> None:
    policy = _comprehensive(_rider("골절진단비", 300000, "FRACTURE_DIAGNOSIS"))
    result = evaluate_claim("u", [policy], RULES, ClaimInput())
    assert result.matched_benefits[0].status == "NOT_EVALUATED"
    assert "KCD 코드" in result.matched_benefits[0].basis


def test_splint_is_excluded_from_cast_benefit() -> None:
    policy = _comprehensive(_rider("깁스치료비", 500000, "CAST_TREATMENT"))
    splint = evaluate_claim(
        "u", [policy], RULES, ClaimInput(treatment_name="부목(반깁스)", treatment_code="T6010")
    )
    assert splint.matched_benefits[0].status == "EXCLUDED"
    plaster = evaluate_claim("u", [policy], RULES, ClaimInput(treatment_name="석고붕대(통깁스)"))
    assert plaster.matched_benefits[0].status == "ELIGIBLE"
    assert plaster.total_estimated_payout == 500000


def test_flu_by_drug_and_by_kcd() -> None:
    policy = _comprehensive(_rider("독감치료비", 200000, "FLU_ANTIVIRAL"))
    by_drug = evaluate_claim("u", [policy], RULES, ClaimInput(prescribed_drugs=["타미플루"]))
    assert by_drug.total_estimated_payout == 200000
    by_kcd = evaluate_claim("u", [policy], RULES, ClaimInput(kcd_code="J10.1"))
    assert by_kcd.total_estimated_payout == 200000
    none = evaluate_claim("u", [policy], RULES, ClaimInput(kcd_code="S82.1"))
    assert none.matched_benefits == []
