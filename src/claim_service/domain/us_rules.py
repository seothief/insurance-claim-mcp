"""Match one US supplemental (fixed-benefit) rule against a claim.

``rule.rule_config`` here is always the rider's schedule of benefits from the policy certificate
(the evaluator only calls this with a certified override). A required schedule field that is
missing returns NOT_EVALUATED instead of a guess. No I/O happens here. Amounts are whole dollars.
"""

from typing import Any

from claim_service.domain.icd10cm import match_icd10, schedule_amount
from claim_service.domain.models import ClaimInput, CoverageRule, PolicyOut, RiderOut
from claim_service.domain.outcome import Outcome, make_outcome

_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "US_HOSPITAL_CONFINEMENT": ("max_days",),
    "US_ICU_CONFINEMENT": ("max_days",),
    "US_CRITICAL_ILLNESS": ("target_icd10_prefixes",),
    "US_ACCIDENT_FRACTURE": ("schedule",),
}


def evaluate_us_rider(
    rule: CoverageRule, policy: PolicyOut, rider: RiderOut, claim: ClaimInput
) -> Outcome | None:
    """Return an Outcome when the rider is relevant to the claim, otherwise None."""
    cfg: dict[str, Any] = rule.rule_config
    name = rider.rider_name
    amount = rider.coverage_amount
    rule_id = rule.rule_id
    icd = (claim.icd10_code or "").strip()

    missing_schedule = [key for key in _REQUIRED_FIELDS.get(rule_id, ()) if key not in cfg]
    if missing_schedule:
        return make_outcome(
            policy, name, rule_id, "NOT_EVALUATED", 0,
            f"Schedule of benefits is missing {', '.join(missing_schedule)}; not calculated.",
        )

    missing_fact: str | None = None
    if rule_id in {"US_HOSPITAL_ADMISSION", "US_HOSPITAL_CONFINEMENT"}:
        if claim.is_inpatient is None:
            missing_fact = "whether the patient was admitted as an inpatient"
        elif rule_id == "US_HOSPITAL_CONFINEMENT" and claim.is_inpatient and (
            claim.inpatient_days is None
        ):
            missing_fact = "the number of inpatient days"
    elif rule_id == "US_ICU_CONFINEMENT" and claim.icu_days is None:
        missing_fact = "the number of ICU days"
    elif rule_id == "US_CRITICAL_ILLNESS" and not icd:
        missing_fact = "the ICD-10-CM diagnosis code"
    elif rule_id == "US_ACCIDENT_FRACTURE":
        if claim.is_injury is None:
            missing_fact = "whether the condition was caused by an accident"
        elif not icd:
            missing_fact = "the ICD-10-CM diagnosis code"
    elif rule_id == "US_EMERGENCY_ROOM":
        if claim.is_emergency is None:
            missing_fact = "whether this was an emergency room visit"
        elif cfg.get("injury_only") and claim.is_injury is None:
            missing_fact = "whether the ER visit was caused by an accident"

    if missing_fact:
        return make_outcome(
            policy, name, rule_id, "NOT_EVALUATED", 0,
            f"Not calculated: {missing_fact} was not established.",
        )

    excluded = [str(p) for p in cfg.get("exclude_icd10_prefixes", [])]
    if icd and excluded and match_icd10(icd, excluded):
        return make_outcome(
            policy, name, rule_id, "EXCLUDED", 0,
            f"ICD-10-CM code '{icd}' is excluded by this policy's schedule of benefits.",
        )

    if rule_id == "US_HOSPITAL_ADMISSION":
        if claim.is_inpatient:
            return make_outcome(
                policy, name, rule_id, "ELIGIBLE", amount,
                f"Inpatient admission confirmed: ${amount:,} per admission.",
            )
        return None

    if rule_id == "US_HOSPITAL_CONFINEMENT":
        if not claim.is_inpatient or not claim.inpatient_days:
            return None
        max_days = int(cfg["max_days"])
        elimination = int(cfg.get("elimination_days", 0))
        days = max(0, min(claim.inpatient_days, max_days) - elimination)
        if days == 0:
            return make_outcome(
                policy, name, rule_id, "EXCLUDED", 0,
                f"{claim.inpatient_days} inpatient day(s) fall within the "
                f"{elimination}-day elimination period.",
            )
        return make_outcome(
            policy, name, rule_id, "ELIGIBLE", amount * days,
            f"{days} payable day(s) x ${amount:,}/day "
            f"(stay {claim.inpatient_days} days, max {max_days}, elimination {elimination}).",
        )

    if rule_id == "US_ICU_CONFINEMENT":
        if not claim.icu_days:
            return None
        max_days = int(cfg["max_days"])
        days = min(claim.icu_days, max_days)
        return make_outcome(
            policy, name, rule_id, "ELIGIBLE", amount * days,
            f"{days} ICU day(s) x ${amount:,}/day (max {max_days}).",
        )

    if rule_id == "US_CRITICAL_ILLNESS":
        targets = [str(p) for p in cfg["target_icd10_prefixes"]]
        if not match_icd10(icd, targets):
            return None
        percent = int(cfg.get("benefit_percent", 100))
        payout = amount * percent // 100
        return make_outcome(
            policy, name, rule_id, "ELIGIBLE", payout,
            f"ICD-10-CM '{icd}' is a covered condition: {percent}% of ${amount:,} face amount.",
        )

    if rule_id == "US_ACCIDENT_FRACTURE":
        if not claim.is_injury:
            return make_outcome(
                policy, name, rule_id, "EXCLUDED", 0,
                "Accident fracture benefits require an accidental injury.",
            )
        hit = schedule_amount(icd, dict(cfg["schedule"]))
        if hit is None:
            return None
        prefix, payout = hit
        return make_outcome(
            policy, name, rule_id, "ELIGIBLE", payout,
            f"ICD-10-CM '{icd}' matches schedule line '{prefix}': ${payout:,}.",
        )

    if rule_id == "US_EMERGENCY_ROOM":
        if not claim.is_emergency:
            return None
        if cfg.get("injury_only") and not claim.is_injury:
            return make_outcome(
                policy, name, rule_id, "EXCLUDED", 0,
                "This ER benefit pays only for accident-related visits.",
            )
        return make_outcome(
            policy, name, rule_id, "ELIGIBLE", amount,
            f"Emergency room visit confirmed: ${amount:,}.",
        )

    return None
