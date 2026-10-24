"""Domain models shared by the repository, evaluator, service, REST API and MCP tools."""

from typing import Any, Literal

from pydantic import BaseModel, Field

PolicyType = Literal["SILSON", "COMPREHENSIVE", "FIXED_BENEFIT", "DENTAL", "DRIVER", "OTHER"]
HospitalType = Literal["clinic", "hospital", "general"]
BenefitStatus = Literal["ELIGIBLE", "EXCLUDED", "NOT_EVALUATED"]
RuleCategory = Literal["INDEMNITY_SILSON", "FIXED_BENEFIT"]
MappingStatus = Literal["MAPPED", "NEEDS_CLARIFICATION", "CUSTOM", "IGNORED"]
ResolvableStatus = Literal["MAPPED", "CUSTOM", "IGNORED"]
OnboardingStatus = Literal["CREATED", "NEEDS_CLARIFICATION", "READY"]
RegistrationAction = Literal["CREATED", "UPDATED"]
USER_ID_PATTERN = r"^[A-Za-z0-9_-]+$"


class CoverageRule(BaseModel):
    """Standard coverage rule. `verified` stays False until checked against the policy text."""

    rule_id: str
    category: RuleCategory
    display_name: str
    match_keywords: list[str] = Field(default_factory=list)
    rule_config: dict[str, Any] = Field(default_factory=dict)
    required_documents: list[str] = Field(default_factory=list)
    verified: bool = False
    source_reference: str


class UserIn(BaseModel):
    user_id: str = Field(min_length=1, max_length=64, pattern=USER_ID_PATTERN)
    display_alias: str | None = Field(default=None, max_length=100)
    birth_year: int | None = Field(default=None, ge=1900, le=2100)
    pin: str | None = Field(default=None, min_length=4, max_length=32)


class UnresolvedRider(BaseModel):
    """A rider that needs AI or user confirmation before it can be evaluated."""

    rider_id: str
    rider_name: str
    candidate_rules: list[str] = Field(default_factory=list)


class UserProfile(BaseModel):
    user_id: str
    display_alias: str | None = None
    birth_year: int | None = None
    pin_protected: bool = False
    onboarding_status: OnboardingStatus
    policy_count: int
    rider_count: int
    resolved_rider_count: int
    unresolved_riders: list[UnresolvedRider] = Field(default_factory=list)
    next_step: str


SourceType = Literal["POLICY_CERTIFICATE", "USER_STATED", "SYNTHETIC_SAMPLE"]
SOURCE_LABELS: dict[str, str] = {
    "POLICY_CERTIFICATE": "보험증권 근거 (사용자가 증권이라고 제출)",
    "USER_STATED": "사용자 진술 (증권 근거 없음 — 계산하지 않음)",
    "SYNTHETIC_SAMPLE": "합성 샘플 (실제 보험 아님 — 계산하지 않음)",
}


class RiderIn(BaseModel):
    """A rider as read from a document. Only POLICY_CERTIFICATE may be used for calculation."""

    rider_name: str = Field(min_length=1, max_length=200)
    coverage_amount: int = Field(ge=0)
    source_type: SourceType = "USER_STATED"
    issuer: str | None = Field(default=None, max_length=100)
    issued_on: str | None = Field(default=None, max_length=10, pattern=r"^\d{4}-\d{2}-\d{2}$")
    # 약관/증권에서 확인한 이 특약만의 지급 요건(rule_config 오버라이드).
    # POLICY_CERTIFICATE 특약에서만 계산 근거로 쓰고, None이면 표준 규칙의 rule_config를 쓴다.
    rule_config_override: dict[str, Any] | None = None


class PolicyIn(BaseModel):
    company: str = Field(min_length=1, max_length=100)
    product_name: str = Field(min_length=1, max_length=200)
    policy_type: PolicyType
    silson_generation: int | None = Field(default=None, ge=1, le=4)
    enrolled_year: int | None = Field(default=None, ge=1980, le=2100)
    riders: list[RiderIn] = Field(default_factory=list)
    replace_riders: bool = False
    # Source of the policy-level facts (product, generation). Calculated only when certified.
    source_type: SourceType = "USER_STATED"
    issuer: str | None = Field(default=None, max_length=100)
    issued_on: str | None = Field(default=None, max_length=10, pattern=r"^\d{4}-\d{2}-\d{2}$")


class RiderOut(BaseModel):
    rider_id: str
    rider_name: str
    coverage_amount: int
    mapped_rule_id: str | None = None
    mapping_status: MappingStatus = "MAPPED"
    custom_rule_config: dict[str, Any] | None = None
    source_type: SourceType = "USER_STATED"
    issuer: str | None = None
    issued_on: str | None = None
    rule_config_override: dict[str, Any] | None = None

    @property
    def is_source_verified(self) -> bool:
        """Only a policy certificate may be used for calculation (strict rule)."""
        return self.source_type == "POLICY_CERTIFICATE"


class PolicyOut(BaseModel):
    policy_id: str
    company: str
    product_name: str
    policy_type: PolicyType
    silson_generation: int | None = None
    enrolled_year: int | None = None
    riders: list[RiderOut] = Field(default_factory=list)
    source_type: SourceType = "USER_STATED"
    issuer: str | None = None
    issued_on: str | None = None

    @property
    def is_source_verified(self) -> bool:
        return self.source_type == "POLICY_CERTIFICATE"


class PolicyRegistration(BaseModel):
    """Result of registering a policy. Unresolved riders come with a follow-up prompt for the AI."""

    action: RegistrationAction
    policy: PolicyOut
    unresolved_riders: list[UnresolvedRider] = Field(default_factory=list)
    ai_follow_up_prompt: str | None = None


class RiderUpdate(BaseModel):
    coverage_amount: int = Field(ge=0)


class RiderResolve(BaseModel):
    """Confirmed mapping for a rider: a standard rule, a custom condition, or ignored."""

    mapping_status: ResolvableStatus
    mapped_rule_id: str | None = None
    custom_rule_config: dict[str, Any] | None = None
    coverage_amount: int | None = Field(default=None, ge=0)
    # 증권/약관에서 확인한 특약별 지급 요건. POLICY_CERTIFICATE 특약에서 계산에 반영된다.
    rule_config_override: dict[str, Any] | None = None


class ClaimInput(BaseModel):
    """Values extracted from receipts/prescriptions. Used for one evaluation and never stored."""

    kcd_code: str | None = None
    treatment_name: str | None = None
    treatment_code: str | None = None
    cost_covered: int = Field(default=0, ge=0)
    cost_uncovered: int = Field(default=0, ge=0)
    hospital_type: HospitalType | None = None
    # None means the receipt/prescription did not establish this fact.
    is_inpatient: bool | None = None
    inpatient_days: int | None = Field(default=None, ge=0)
    is_injury: bool | None = None
    is_emergency: bool | None = None
    prescribed_drugs: list[str] = Field(default_factory=list)


class BenefitResult(BaseModel):
    rider_name: str
    company: str
    status: BenefitStatus
    estimated_amount: int
    basis: str


class ClaimEvaluation(BaseModel):
    user_id: str
    matched_benefits: list[BenefitResult]
    total_estimated_payout: int
    required_documents: list[str]
    pending_riders: list[str] = Field(default_factory=list)
    # Riders that exist but have no policy-certificate source. They are never calculated.
    unverified_source_riders: list[str] = Field(default_factory=list)
    disclaimer: str
