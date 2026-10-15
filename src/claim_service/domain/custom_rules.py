"""Evaluate a rider whose conditions were confirmed by the user or by the registration AI.

Custom conditions are not part of the standard catalog, so their basis always says they are
unverified. No I/O happens here.
"""

from typing import Any

from claim_service.domain.models import ClaimInput, PolicyOut, RiderOut
from claim_service.domain.outcome import Outcome, make_outcome

UNVERIFIED_NOTE = "사용자 또는 등록 AI가 확정한 커스텀 조건이며 약관 원문으로 검증되지 않았습니다."


def evaluate_custom_rider(policy: PolicyOut, rider: RiderOut, claim: ClaimInput) -> Outcome | None:
    cfg: dict[str, Any] = rider.custom_rule_config or {}
    kcd = (claim.kcd_code or "").strip().upper()
    treatment_text = (claim.treatment_name or "") + (claim.treatment_code or "")

    if kcd and any(kcd.startswith(str(ex).upper()) for ex in cfg.get("exclusion_kcd", [])):
        return make_outcome(
            policy, rider.rider_name, None, "EXCLUDED", 0,
            f"KCD 코드 '{kcd}'는 커스텀 조건의 제외 대상입니다. {UNVERIFIED_NOTE}",
        )
    kcd_hit = bool(kcd) and any(
        kcd.startswith(str(prefix).upper()) for prefix in cfg.get("target_kcd_prefixes", [])
    )
    keyword_hit = any(
        bool(keyword) and str(keyword) in treatment_text
        for keyword in cfg.get("target_keywords", [])
    )
    if kcd_hit or keyword_hit:
        return make_outcome(
            policy, rider.rider_name, None, "ELIGIBLE", rider.coverage_amount,
            f"커스텀 조건을 충족했습니다. {UNVERIFIED_NOTE}",
        )
    return None
