"""Application service: onboarding, policy registration with AI feedback, and claim evaluation."""

from collections.abc import Sequence
from typing import Any

from claim_service.db.repository import PolicyRepository, RiderPlan
from claim_service.domain.catalog import candidate_rule_ids, match_fixed_rule
from claim_service.domain.errors import ConflictError, InvalidMappingError, NotFoundError
from claim_service.domain.evaluator import evaluate_claim
from claim_service.domain.models import (
    ClaimEvaluation,
    ClaimInput,
    CoverageRule,
    OnboardingStatus,
    PolicyIn,
    PolicyOut,
    PolicyRegistration,
    RiderIn,
    RiderOut,
    RiderResolve,
    UnresolvedRider,
    UserIn,
    UserProfile,
)
from claim_service.domain.onboarding import (
    build_follow_up_prompt,
    build_onboarding_guide,
    next_step_message,
)
from claim_service.domain.silson import resolve_silson_generation


class PolicyService:
    def __init__(self, repository: PolicyRepository) -> None:
        self._repo = repository

    def rules(self) -> dict[str, CoverageRule]:
        return self._repo.get_rules()

    def onboarding_guide(self) -> dict[str, object]:
        return build_onboarding_guide(self._repo.get_rules().values())

    # ---- onboarding -----------------------------------------------------
    def register_user(self, user: UserIn) -> UserProfile:
        if not self._repo.create_user(user):
            raise ConflictError(f"이미 등록된 사용자입니다: {user.user_id}")
        return self.user_profile(user.user_id)

    def user_profile(self, user_id: str) -> UserProfile:
        record = self._repo.get_user(user_id)
        if record is None:
            raise NotFoundError(f"사용자를 찾을 수 없습니다: {user_id}")
        policies = self._repo.list_policies(user_id)
        rules = self._repo.get_rules()
        riders = [rider for policy in policies for rider in policy.riders]
        unresolved = self._unresolved(riders, rules)
        resolved_count = sum(
            1 for rider in riders if rider.mapping_status != "NEEDS_CLARIFICATION"
        )
        status: OnboardingStatus
        if not policies:
            status = "CREATED"
        elif unresolved:
            status = "NEEDS_CLARIFICATION"
        else:
            status = "READY"
        return UserProfile(
            user_id=user_id,
            display_alias=record["display_alias"],
            birth_year=record["birth_year"],
            onboarding_status=status,
            policy_count=len(policies),
            rider_count=len(riders),
            resolved_rider_count=resolved_count,
            unresolved_riders=unresolved,
            next_step=next_step_message(status, len(unresolved)),
        )

    # ---- policies -------------------------------------------------------
    def register_policy(self, user_id: str, policy: PolicyIn) -> PolicyRegistration:
        """Register or update a policy. Riders that cannot be mapped come back for AI follow-up."""
        self._repo.ensure_user(user_id)
        rules = self._repo.get_rules()
        generation, note = resolve_silson_generation(policy.silson_generation, policy.enrolled_year)
        draft = PolicyOut(
            policy_id="",
            company=policy.company,
            product_name=policy.product_name,
            policy_type=policy.policy_type,
            silson_generation=generation,
            enrolled_year=policy.enrolled_year,
        )
        plan = [self._plan_rider(rider, rules) for rider in policy.riders]
        action, stored = self._repo.save_policy(
            user_id, draft, plan, replace_riders=policy.replace_riders
        )
        unresolved = self._unresolved(stored.riders, rules)
        prompt = build_follow_up_prompt(policy.company, unresolved) if unresolved else None
        if note:
            prompt = f"{prompt}\n[실손 세대] {note}" if prompt else f"[실손 세대] {note}"
        return PolicyRegistration(
            action=action,
            policy=stored,
            unresolved_riders=unresolved,
            ai_follow_up_prompt=prompt,
        )

    def list_policies(self, user_id: str) -> list[PolicyOut]:
        return self._repo.list_policies(user_id)

    def delete_policy(self, user_id: str, policy_id: str) -> bool:
        return self._repo.delete_policy(user_id, policy_id)

    def update_rider_amount(self, user_id: str, rider_id: str, amount: int) -> bool:
        return self._repo.update_rider(user_id, rider_id, {"coverage_amount": amount})

    def resolve_rider(self, user_id: str, rider_id: str, body: RiderResolve) -> RiderOut:
        """Confirm a rider's mapping. Called after the registering AI re-checks the policy."""
        if self._repo.get_rider(user_id, rider_id) is None:
            raise NotFoundError("특약을 찾을 수 없습니다.")
        values = self._resolve_values(body, self._repo.get_rules())
        self._repo.update_rider(user_id, rider_id, values)
        updated = self._repo.get_rider(user_id, rider_id)
        if updated is None:  # pragma: no cover - ownership was verified above
            raise NotFoundError("특약을 찾을 수 없습니다.")
        return updated

    # ---- helpers --------------------------------------------------------
    @staticmethod
    def _unresolved(
        riders: Sequence[RiderOut], rules: dict[str, CoverageRule]
    ) -> list[UnresolvedRider]:
        return [
            UnresolvedRider(
                rider_id=rider.rider_id,
                rider_name=rider.rider_name,
                candidate_rules=candidate_rule_ids(rider.rider_name, rules.values()),
            )
            for rider in riders
            if rider.mapping_status == "NEEDS_CLARIFICATION"
        ]

    @staticmethod
    def _plan_rider(rider: RiderIn, rules: dict[str, CoverageRule]) -> RiderPlan:
        """Automatic matching never overrides a mapping the user or AI already confirmed.

        Keyword matches are written as non-explicit so an existing confirmed mapping is kept on
        re-registration. Riders with no keyword match are flagged for AI clarification.
        """
        matched = match_fixed_rule(rider.rider_name, rules.values())
        return RiderPlan(
            rider_name=rider.rider_name,
            coverage_amount=rider.coverage_amount,
            mapped_rule_id=matched,
            mapping_status="MAPPED" if matched else "NEEDS_CLARIFICATION",
            custom_rule_config=None,
            explicit_mapping=False,
        )

    @staticmethod
    def _resolve_values(body: RiderResolve, rules: dict[str, CoverageRule]) -> dict[str, Any]:
        values: dict[str, Any] = {"mapping_status": body.mapping_status}
        if body.mapping_status == "MAPPED":
            rule = rules.get(body.mapped_rule_id or "")
            if rule is None:
                raise InvalidMappingError("mapped_rule_id는 존재하는 표준 규칙 ID여야 합니다.")
            if rule.category != "FIXED_BENEFIT":
                raise InvalidMappingError("실손 규칙은 특약에 연결할 수 없습니다.")
            values.update(mapped_rule_id=rule.rule_id, custom_rule_config=None)
        elif body.mapping_status == "CUSTOM":
            if not body.custom_rule_config:
                raise InvalidMappingError("CUSTOM은 custom_rule_config가 필요합니다.")
            values.update(mapped_rule_id=None, custom_rule_config=body.custom_rule_config)
        else:  # IGNORED
            values.update(mapped_rule_id=None, custom_rule_config=None)
        if body.coverage_amount is not None:
            values["coverage_amount"] = body.coverage_amount
        return values

    def evaluate(self, user_id: str, claim: ClaimInput) -> ClaimEvaluation:
        """Evaluate a claim against the user's stored policies. The claim is never persisted."""
        policies = self._repo.list_policies(user_id)
        return evaluate_claim(user_id, policies, self._repo.get_rules(), claim)
