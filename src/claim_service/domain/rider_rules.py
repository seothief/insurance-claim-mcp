"""Match one standard FIXED_BENEFIT rule against a claim.

Each branch is a deterministic rule from the standard catalog. No I/O happens here.
"""

from typing import Any

from claim_service.domain.models import ClaimInput, CoverageRule, PolicyOut, RiderOut
from claim_service.domain.outcome import Outcome, make_outcome


def evaluate_rider(
    rule: CoverageRule, policy: PolicyOut, rider: RiderOut, claim: ClaimInput
) -> Outcome | None:
    """Return an Outcome when the rider is relevant to the claim, otherwise None."""
    cfg: dict[str, Any] = rule.rule_config
    kcd = (claim.kcd_code or "").strip().upper()
    treatment = claim.treatment_name or ""
    treatment_text = treatment + (claim.treatment_code or "")
    name = rider.rider_name
    amount = rider.coverage_amount
    rule_id = rule.rule_id

    missing_fact: str | None = None
    if rule_id in {"FRACTURE_DIAGNOSIS", "BURN_DIAGNOSIS"} and not kcd:
        missing_fact = "진단 KCD 코드"
    elif rule_id == "CAST_TREATMENT" and not treatment_text:
        missing_fact = "깁스 처치명 또는 처치 코드"
    elif rule_id == "FLU_ANTIVIRAL" and not kcd and not claim.prescribed_drugs:
        missing_fact = "진단 KCD 코드 또는 처방 약품명"
    elif rule_id in {"DISEASE_SURGERY", "WOUND_SUTURE"} and not treatment:
        missing_fact = "처치명"
    elif rule_id == "INJURY_SURGERY":
        if claim.is_injury is None:
            missing_fact = "상해 여부"
        elif not treatment:
            missing_fact = "수술명 또는 처치명"
    elif rule_id == "INPATIENT_DAILY":
        if claim.is_inpatient is None:
            missing_fact = "입원 여부"
        elif claim.is_inpatient and claim.inpatient_days is None:
            missing_fact = "입원 일수"
    elif rule_id == "EMERGENCY_ROOM_VISIT" and claim.is_emergency is None:
        missing_fact = "응급실 내원 및 응급 여부"

    if missing_fact:
        return make_outcome(
            policy,
            name,
            rule_id,
            "NOT_EVALUATED",
            0,
            f"{missing_fact}가 확인되지 않아 계산하지 않았습니다.",
        )

    if rule_id == "FRACTURE_DIAGNOSIS":
        if any(kcd.startswith(ex) for ex in cfg["exclusion_kcd"]):
            return make_outcome(
                policy, name, rule_id, "EXCLUDED", 0,
                f"KCD 코드 '{kcd}'는 약관상 보장 제외 대상입니다.",
            )
        if any(kcd.startswith(prefix) for prefix in cfg["target_kcd_prefixes"]):
            return make_outcome(
                policy, name, rule_id, "ELIGIBLE", amount,
                f"KCD 코드 '{kcd}'가 골절 보장 분류에 해당합니다.",
            )
        return None

    if rule_id == "CAST_TREATMENT":
        if any(ex.lower() in treatment_text.lower() for ex in cfg["exclusion_keywords"]):
            return make_outcome(
                policy, name, rule_id, "EXCLUDED", 0,
                "약관상 '석고붕대(통깁스)' 치료만 보장되며, '부목(반깁스)' 치료는 제외됩니다.",
            )
        if any(code in treatment_text for code in cfg["target_edi_codes"]) or (
            "통깁스" in treatment_text
        ):
            return make_outcome(
                policy, name, rule_id, "ELIGIBLE", amount,
                "석고붕대(통깁스) 처치 확인으로 지급 요건을 충족합니다.",
            )
        return None

    if rule_id == "FLU_ANTIVIRAL":
        kcd_match = any(kcd.startswith(prefix) for prefix in cfg["target_kcd_prefixes"])
        drugs_text = "".join(claim.prescribed_drugs)
        drug_match = any(drug in drugs_text for drug in cfg["antiviral_drugs"])
        if kcd_match or drug_match:
            return make_outcome(
                policy, name, rule_id, "ELIGIBLE", amount,
                "독감 코드 또는 항바이러스제 처방이 확인되어 지급 요건에 해당합니다.",
            )
        return None

    if rule_id == "DISEASE_SURGERY":
        if any(keyword in treatment for keyword in cfg["target_keywords"]):
            return make_outcome(
                policy, name, rule_id, "ELIGIBLE", amount,
                f"시술/수술 내용('{treatment}')이 질병 수술 정의에 해당합니다.",
            )
        return None

    if rule_id == "INJURY_SURGERY":
        if claim.is_injury and "수술" in treatment:
            return make_outcome(
                policy, name, rule_id, "ELIGIBLE", amount,
                "상해로 인한 수술로 확인되어 지급 요건에 해당합니다.",
            )
        return None

    if rule_id == "BURN_DIAGNOSIS":
        if any(kcd.startswith(prefix) for prefix in cfg["target_kcd_prefixes"]):
            return make_outcome(
                policy, name, rule_id, "ELIGIBLE", amount,
                f"KCD 코드 '{kcd}'가 화상 보장 분류에 해당합니다.",
            )
        return None

    if rule_id == "WOUND_SUTURE":
        if any(keyword in treatment for keyword in cfg["target_keywords"]):
            return make_outcome(
                policy, name, rule_id, "ELIGIBLE", amount,
                f"처치 내용('{treatment}')이 창상봉합 보장에 해당합니다.",
            )
        return None

    if rule_id == "INPATIENT_DAILY":
        if claim.is_inpatient and claim.inpatient_days is not None and claim.inpatient_days >= 1:
            days = claim.inpatient_days
            return make_outcome(
                policy, name, rule_id, "ELIGIBLE", amount * days,
                f"입원 {days}일 × 가입금액 {amount:,}원을 1일 지급액으로 가정해 계산했습니다. "
                "1일 지급 기준은 약관 대조 전입니다.",
            )
        return None

    if rule_id == "EMERGENCY_ROOM_VISIT":
        if claim.is_emergency:
            return make_outcome(
                policy, name, rule_id, "ELIGIBLE", amount,
                "응급실 내원 진료로 확인되어 지급 요건에 해당합니다.",
            )
        return None

    return None
