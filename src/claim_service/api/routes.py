"""REST routes: onboarding, policy registration with AI feedback, and claim evaluation."""

from fastapi import APIRouter, HTTPException, Response, status

from claim_service.domain.errors import (
    ConflictError,
    DomainError,
    InvalidMappingError,
    NotFoundError,
)
from claim_service.domain.models import (
    ClaimEvaluation,
    ClaimInput,
    CoverageRule,
    PolicyIn,
    PolicyOut,
    PolicyRegistration,
    RiderOut,
    RiderResolve,
    RiderUpdate,
    UserIn,
    UserProfile,
)
from claim_service.runtime import get_service

router = APIRouter(prefix="/api")


def _raise_http(exc: DomainError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, InvalidMappingError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/catalog/rules", response_model=list[CoverageRule])
def list_rules() -> list[CoverageRule]:
    return list(get_service().rules().values())


@router.get("/onboarding/guide")
def onboarding_guide() -> dict[str, object]:
    return get_service().onboarding_guide()


@router.post("/users", response_model=UserProfile, status_code=status.HTTP_201_CREATED)
def register_user(body: UserIn) -> UserProfile:
    try:
        return get_service().register_user(body)
    except DomainError as exc:
        raise _raise_http(exc) from exc


@router.get("/users/{user_id}", response_model=UserProfile)
def get_user_profile(user_id: str) -> UserProfile:
    try:
        return get_service().user_profile(user_id)
    except DomainError as exc:
        raise _raise_http(exc) from exc


@router.post(
    "/users/{user_id}/policies",
    response_model=PolicyRegistration,
)
def register_policy(user_id: str, body: PolicyIn) -> PolicyRegistration:
    """Register a policy. Same company and product name updates the existing policy."""
    try:
        return get_service().register_policy(user_id, body)
    except DomainError as exc:
        raise _raise_http(exc) from exc


@router.get("/users/{user_id}/policies", response_model=list[PolicyOut])
def list_policies(user_id: str) -> list[PolicyOut]:
    return get_service().list_policies(user_id)


@router.delete(
    "/users/{user_id}/policies/{policy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_policy(user_id: str, policy_id: str) -> Response:
    if not get_service().delete_policy(user_id, policy_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="policy not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/users/{user_id}/riders/{rider_id}", status_code=status.HTTP_204_NO_CONTENT)
def update_rider(user_id: str, rider_id: str, body: RiderUpdate) -> Response:
    if not get_service().update_rider_amount(user_id, rider_id, body.coverage_amount):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="rider not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/users/{user_id}/riders/{rider_id}/resolve", response_model=RiderOut)
def resolve_rider(user_id: str, rider_id: str, body: RiderResolve) -> RiderOut:
    """Confirm a rider's mapping after the registering AI re-checks the policy."""
    try:
        return get_service().resolve_rider(user_id, rider_id, body)
    except DomainError as exc:
        raise _raise_http(exc) from exc


@router.post("/users/{user_id}/evaluate", response_model=ClaimEvaluation)
def evaluate(user_id: str, body: ClaimInput) -> ClaimEvaluation:
    """Evaluate a claim. The request is not stored; only informational estimates are returned."""
    return get_service().evaluate(user_id, body)
