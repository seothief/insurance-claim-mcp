"""Application service: onboarding, policy registration with AI feedback, and claim evaluation."""

from collections.abc import Sequence
from typing import Any

from claim_service.db.repository import PolicyRepository, RiderPlan
from claim_service.domain.catalog import candidate_rule_ids, match_fixed_rule
from claim_service.domain.errors import (
    AccessDeniedError,
    ConflictError,
    InvalidMappingError,
    NotFoundError,
)
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
from claim_service.domain.security import (
    get_bound_user,
    get_header_pin,
    hash_pin,
    verify_pin,
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
        self._check_bound_user(user.user_id)
        effective_pin = user.pin or get_header_pin()
        pin_hashed = hash_pin(effective_pin) if effective_pin else None
        if not self._repo.create_user(user, pin_hash=pin_hashed):
            raise ConflictError(
                f"이미 등록된 사용자입니다 ({user.user_id}). "
                "본인이 맞다면 PIN과 함께 조회하고, 처음이시면 다른 별명을 사용해 주세요."
            )
        return self.user_profile(user.user_id, pin=effective_pin)

    def user_profile(self, user_id: str, pin: str | None = None) -> UserProfile:
        record = self._require_authorized_user(user_id, pin)
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
            pin_protected=bool(record.get("pin_hash")),
            onboarding_status=status,
            policy_count=len(policies),
            rider_count=len(riders),
            resolved_rider_count=resolved_count,
            unresolved_riders=unresolved,
            next_step=next_step_message(status, len(unresolved)),
        )

    # ---- policies -------------------------------------------------------
    def register_policy(
        self, user_id: str, policy: PolicyIn, pin: str | None = None
    ) -> PolicyRegistration:
        """Register or update a policy. Riders that cannot be mapped come back for AI follow-up."""
        self._ensure_authorized_user(user_id, pin)
        rules = self._repo.get_rules()
        generation, note = resolve_silson_generation(policy.silson_generation, policy.enrolled_year)
        draft = PolicyOut(
            policy_id="",
            company=policy.company,
            product_name=policy.product_name,
            policy_type=policy.policy_type,
            silson_generation=generation,
            enrolled_year=policy.enrolled_year,
            source_type=policy.source_type,
            issuer=policy.issuer,
            issued_on=policy.issued_on,
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

    def list_policies(self, user_id: str, pin: str | None = None) -> list[PolicyOut]:
        self._verify_existing_if_present(user_id, pin)
        return self._repo.list_policies(user_id)

    def delete_policy(self, user_id: str, policy_id: str, pin: str | None = None) -> bool:
        self._verify_existing_if_present(user_id, pin)
        return self._repo.delete_policy(user_id, policy_id)

    def update_rider_amount(
        self, user_id: str, rider_id: str, amount: int, pin: str | None = None
    ) -> bool:
        self._verify_existing_if_present(user_id, pin)
        return self._repo.update_rider(user_id, rider_id, {"coverage_amount": amount})

    def resolve_rider(
        self, user_id: str, rider_id: str, body: RiderResolve, pin: str | None = None
    ) -> RiderOut:
        """Confirm a rider's mapping. Called after the registering AI re-checks the policy."""
        self._verify_existing_if_present(user_id, pin)
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
            source_type=rider.source_type,
            issuer=rider.issuer,
            issued_on=rider.issued_on,
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

    def evaluate(
        self, user_id: str, claim: ClaimInput, pin: str | None = None
    ) -> ClaimEvaluation:
        """Evaluate a claim against the user's stored policies. The claim is never persisted."""
        self._verify_existing_if_present(user_id, pin)
        policies = self._repo.list_policies(user_id)
        return evaluate_claim(user_id, policies, self._repo.get_rules(), claim)

    # ---- access control helpers -----------------------------------------
    @staticmethod
    def _check_bound_user(user_id: str) -> None:
        bound = get_bound_user()
        if bound and bound != user_id:
            raise AccessDeniedError(
                f"현재 연결은 '{bound}' 전용으로 귀속되어 '{user_id}'에 접근할 수 없습니다."
            )

    def _require_authorized_user(self, user_id: str, pin: str | None) -> dict[str, Any]:
        self._check_bound_user(user_id)
        record = self._repo.get_user(user_id)
        if record is None:
            raise NotFoundError(f"사용자를 찾을 수 없습니다: {user_id}")
        self._check_pin(record, pin)
        return record

    def _verify_existing_if_present(self, user_id: str, pin: str | None) -> None:
        self._check_bound_user(user_id)
        record = self._repo.get_user(user_id)
        if record is not None:
            self._check_pin(record, pin)

    def _ensure_authorized_user(self, user_id: str, pin: str | None) -> None:
        self._check_bound_user(user_id)
        effective_pin = pin or get_header_pin()
        record = self._repo.get_user(user_id)
        if record is None:
            pin_hashed = hash_pin(effective_pin) if effective_pin else None
            self._repo.ensure_user(user_id, pin_hash=pin_hashed)
            return
        self._check_pin(record, effective_pin)

    @staticmethod
    def _check_pin(record: dict[str, Any], pin: str | None) -> None:
        stored_hash = record.get("pin_hash")
        if not stored_hash:
            return
        candidate = pin or get_header_pin()
        if not candidate or not verify_pin(candidate, str(stored_hash)):
            raise AccessDeniedError(
                "이미 다른 사용자가 사용 중인 별명이거나 PIN 번호가 일치하지 않습니다."
            )
