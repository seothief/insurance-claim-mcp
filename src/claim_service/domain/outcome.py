"""Shared result type for a single benefit evaluation."""

from dataclasses import dataclass

from claim_service.domain.models import BenefitResult, BenefitStatus, PolicyOut


@dataclass(frozen=True)
class Outcome:
    result: BenefitResult
    rule_id: str | None


def make_outcome(
    policy: PolicyOut,
    rider_name: str,
    rule_id: str | None,
    status: BenefitStatus,
    amount: int,
    basis: str,
) -> Outcome:
    return Outcome(
        result=BenefitResult(
            rider_name=rider_name,
            company=policy.company,
            status=status,
            estimated_amount=amount,
            basis=basis,
        ),
        rule_id=rule_id,
    )
