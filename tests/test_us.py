"""US supplemental (fixed-benefit) plans: ICD-10-CM matching, rules and MCP flow."""

import asyncio
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

from claim_service.domain.catalog import STANDARD_RULES, match_fixed_rule
from claim_service.domain.evaluator import US_DISCLAIMER, evaluate_claim
from claim_service.domain.icd10cm import match_icd10, normalize_icd10, schedule_amount
from claim_service.domain.models import ClaimInput, PolicyOut, RiderOut
from claim_service.mcp.server import mcp

RULES = {rule.rule_id: rule for rule in STANDARD_RULES}


def _rider(
    rule_id: str, amount: int, override: dict[str, Any] | None, name: str | None = None
) -> RiderOut:
    return RiderOut(
        rider_id=f"id-{rule_id}",
        rider_name=name or rule_id,
        coverage_amount=amount,
        mapped_rule_id=rule_id,
        source_type="POLICY_CERTIFICATE",
        rule_config_override=override,
    )


def _policy(*riders: RiderOut, policy_type: str = "US_HOSPITAL_INDEMNITY") -> PolicyOut:
    return PolicyOut(
        policy_id="us-1",
        company="Acme Life",
        product_name="Acme Hospital Plan",
        policy_type=policy_type,  # type: ignore[arg-type]
        riders=list(riders),
        source_type="POLICY_CERTIFICATE",
    )


def _evaluate(policy: PolicyOut, **claim: Any) -> list[tuple[str, int]]:
    result = evaluate_claim("u", [policy], RULES, ClaimInput(**claim))
    return [(b.status, b.estimated_amount) for b in result.matched_benefits]


# ---- ICD-10-CM -----------------------------------------------------------


def test_normalize_icd10_accepts_dotted_and_lowercase() -> None:
    assert normalize_icd10("s72.001a") == "S72001A"
    assert normalize_icd10("I21.4") == "I214"
    with pytest.raises(ValueError):
        normalize_icd10("72.0")


def test_match_icd10_respects_exclusions() -> None:
    assert match_icd10("C50.911", ["C"], excluded=["C44"])
    assert not match_icd10("C44.91", ["C"], excluded=["C44"])
    assert not match_icd10("not-a-code", ["C"])


def test_schedule_amount_prefers_longest_prefix() -> None:
    schedule = {"S72": 4000, "S72.0": 5000, "S62": 500}
    assert schedule_amount("S72.001A", schedule) == ("S720", 5000)
    assert schedule_amount("S72.401A", schedule) == ("S72", 4000)
    assert schedule_amount("S82.0", schedule) is None


# ---- rider name mapping --------------------------------------------------


def test_us_rider_names_map_only_to_us_rules() -> None:
    rules = list(STANDARD_RULES)
    assert match_fixed_rule("Fracture Benefit", rules, "US_FIXED_BENEFIT") == "US_ACCIDENT_FRACTURE"
    assert match_fixed_rule("ICU Confinement", rules, "US_FIXED_BENEFIT") == "US_ICU_CONFINEMENT"
    assert (
        match_fixed_rule("Daily Hospital Confinement", rules, "US_FIXED_BENEFIT")
        == "US_HOSPITAL_CONFINEMENT"
    )
    # Korean policies keep mapping to Korean rules.
    assert match_fixed_rule("Fracture Benefit", rules) == "FRACTURE_DIAGNOSIS"


# ---- fail-closed ---------------------------------------------------------


def test_us_rider_without_schedule_is_not_evaluated() -> None:
    policy = _policy(_rider("US_HOSPITAL_ADMISSION", 1000, override=None))
    assert _evaluate(policy, is_inpatient=True) == [("NOT_EVALUATED", 0)]


def test_us_rider_missing_required_schedule_field_is_not_evaluated() -> None:
    policy = _policy(_rider("US_HOSPITAL_CONFINEMENT", 200, override={}))
    assert _evaluate(policy, is_inpatient=True, inpatient_days=3) == [("NOT_EVALUATED", 0)]


def test_us_rider_missing_claim_fact_is_not_evaluated() -> None:
    policy = _policy(_rider("US_HOSPITAL_CONFINEMENT", 200, override={"max_days": 30}))
    assert _evaluate(policy, is_inpatient=True) == [("NOT_EVALUATED", 0)]


# ---- rules ---------------------------------------------------------------


def test_hospital_admission_and_confinement() -> None:
    policy = _policy(
        _rider("US_HOSPITAL_ADMISSION", 1000, override={}),
        _rider("US_HOSPITAL_CONFINEMENT", 200, override={"max_days": 5, "elimination_days": 1}),
    )
    result = evaluate_claim(
        "u", [policy], RULES, ClaimInput(is_inpatient=True, inpatient_days=8)
    )
    assert [(b.status, b.estimated_amount) for b in result.matched_benefits] == [
        ("ELIGIBLE", 1000),
        ("ELIGIBLE", 800),  # min(8, 5) - 1 elimination day = 4 days x $200
    ]
    assert result.total_estimated_payout == 1800
    assert result.disclaimer == US_DISCLAIMER
    assert "Hospital discharge summary (admission and discharge dates)" in (
        result.required_documents
    )


def test_confinement_inside_elimination_period_is_excluded() -> None:
    policy = _policy(
        _rider("US_HOSPITAL_CONFINEMENT", 200, override={"max_days": 30, "elimination_days": 2})
    )
    assert _evaluate(policy, is_inpatient=True, inpatient_days=2) == [("EXCLUDED", 0)]


def test_icu_days_are_capped() -> None:
    policy = _policy(_rider("US_ICU_CONFINEMENT", 400, override={"max_days": 3}))
    assert _evaluate(policy, icu_days=5) == [("ELIGIBLE", 1200)]


def test_critical_illness_pays_percent_of_face_amount() -> None:
    policy = _policy(
        _rider(
            "US_CRITICAL_ILLNESS",
            20000,
            override={
                "target_icd10_prefixes": ["C"],
                "exclude_icd10_prefixes": ["C44"],
                "benefit_percent": 25,
            },
        ),
        policy_type="US_CRITICAL_ILLNESS",
    )
    assert _evaluate(policy, icd10_code="C50.911") == [("ELIGIBLE", 5000)]
    assert _evaluate(policy, icd10_code="C44.91") == [("EXCLUDED", 0)]
    assert _evaluate(policy, icd10_code="J10.1") == []


def test_accident_fracture_uses_schedule_and_requires_injury() -> None:
    policy = _policy(
        _rider("US_ACCIDENT_FRACTURE", 0, override={"schedule": {"S72": 4000, "S62": 500}}),
        policy_type="US_ACCIDENT",
    )
    assert _evaluate(policy, icd10_code="S72.001A", is_injury=True) == [("ELIGIBLE", 4000)]
    assert _evaluate(policy, icd10_code="S72.001A", is_injury=False) == [("EXCLUDED", 0)]
    assert _evaluate(policy, icd10_code="S72.001A") == [("NOT_EVALUATED", 0)]


def test_emergency_room_injury_only() -> None:
    policy = _policy(
        _rider("US_EMERGENCY_ROOM", 150, override={"injury_only": True}),
        policy_type="US_ACCIDENT",
    )
    assert _evaluate(policy, is_emergency=True, is_injury=True) == [("ELIGIBLE", 150)]
    assert _evaluate(policy, is_emergency=True, is_injury=False) == [("EXCLUDED", 0)]


# ---- MCP end to end ------------------------------------------------------


def test_mcp_us_hospital_plan_flow(client: TestClient) -> None:
    async def flow() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        async with Client(mcp) as mcp_client:
            await mcp_client.call_tool("register_user", {"user_id": "us_user"})
            cert = {
                "source_type": "POLICY_CERTIFICATE",
                "issuer": "Acme Life",
                "issued_on": "2026-01-15",
            }
            registered = await mcp_client.call_tool(
                "register_user_policy",
                {
                    "user_id": "us_user",
                    "company": "Acme Life",
                    "product_name": "Acme Hospital Plan",
                    "policy_type": "US_HOSPITAL_INDEMNITY",
                    **cert,
                    "riders": [
                        {
                            "rider_name": "Hospital Admission Benefit",
                            "coverage_amount": 1000,
                            "rule_config_override": {},
                            **cert,
                        },
                        {
                            "rider_name": "Daily Hospital Confinement",
                            "coverage_amount": 200,
                            "rule_config_override": {"max_days": 30},
                            **cert,
                        },
                    ],
                },
            )
            evaluated = await mcp_client.call_tool(
                "evaluate_claim",
                {
                    "user_id": "us_user",
                    "claim": {"icd10_code": "J18.9", "is_inpatient": True, "inpatient_days": 3},
                },
            )
            guide = await mcp_client.call_tool(
                "get_document_request_guide",
                {"policy_type": "US_HOSPITAL_INDEMNITY", "product_name": "Acme Hospital Plan"},
            )
            return (
                json.loads(registered.content[0].text),
                json.loads(evaluated.content[0].text),
                json.loads(guide.content[0].text),
            )

    registered, evaluated, guide = asyncio.run(flow())
    assert registered["unresolved_riders"] == []
    assert {r["mapped_rule_id"] for r in registered["policy"]["riders"]} == {
        "US_HOSPITAL_ADMISSION",
        "US_HOSPITAL_CONFINEMENT",
    }
    assert evaluated["total_estimated_payout"] == 1600
    assert evaluated["disclaimer"] == US_DISCLAIMER
    assert guide["kind"] == "US_SUPPLEMENTAL"
