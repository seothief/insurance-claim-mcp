"""Per-user API/MCP key lifecycle: hash-only storage, PIN replacement, listing and revocation."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select

from claim_service.db.engine import create_db_engine
from claim_service.db.repository import PolicyRepository
from claim_service.db.tables import user_api_keys
from claim_service.domain.errors import AccessDeniedError, NotFoundError
from claim_service.domain.models import UserIn
from claim_service.domain.security import (
    api_key_prefix,
    generate_api_key,
    hash_api_key,
    hash_pin,
    set_key_authenticated_user,
)
from claim_service.main import create_app
from claim_service.runtime import get_service
from tests.dbutil import database_url_for


@pytest.fixture
def keyed_user(
    tmp_path: Path, fresh_external_schema: None
) -> Iterator[tuple[PolicyRepository, Engine, str, str]]:
    """Fresh DB with one PIN-protected user ("pin_user") holding one active key."""
    database_url = database_url_for(tmp_path, "user_keys.db")
    with TestClient(create_app(database_url)):
        engine = create_db_engine(database_url)
        repo = PolicyRepository(engine)
        repo.create_user(UserIn(user_id="pin_user", pin="4829"), pin_hash=hash_pin("4829"))
        raw_key = generate_api_key()
        key_id = repo.create_api_key("pin_user", hash_api_key(raw_key), api_key_prefix(raw_key))
        yield repo, engine, raw_key, key_id
        engine.dispose()


def test_only_sha256_hash_is_stored(
    keyed_user: tuple[PolicyRepository, Engine, str, str],
) -> None:
    _, engine, raw_key, _ = keyed_user
    with engine.connect() as conn:
        stored = conn.execute(select(user_api_keys.c.key_hash)).scalar_one()
    assert stored == hash_api_key(raw_key)
    assert stored != raw_key
    assert len(stored) == 64


def test_active_key_resolves_to_its_owner(
    keyed_user: tuple[PolicyRepository, Engine, str, str],
) -> None:
    _, _, raw_key, _ = keyed_user
    assert get_service().authenticate_api_key(raw_key) == "pin_user"
    assert get_service().authenticate_api_key("not-a-real-key") is None


def test_valid_key_replaces_pin_entry(
    keyed_user: tuple[PolicyRepository, Engine, str, str],
) -> None:
    _, _, raw_key, _ = keyed_user
    service = get_service()
    # Without the key, the PIN-protected account rejects a PIN-less call.
    with pytest.raises(AccessDeniedError):
        service.user_profile("pin_user")
    # A key proven by the middleware stands in for the PIN.
    assert service.authenticate_api_key(raw_key) == "pin_user"
    set_key_authenticated_user("pin_user")
    try:
        profile = service.user_profile("pin_user")
    finally:
        set_key_authenticated_user(None)
    assert profile.user_id == "pin_user"
    assert profile.pin_protected is True


def test_revoked_key_can_no_longer_authenticate(
    keyed_user: tuple[PolicyRepository, Engine, str, str],
) -> None:
    repo, _, raw_key, key_id = keyed_user
    assert repo.list_api_keys("pin_user")[0]["revoked_at"] is None
    assert repo.revoke_api_key("pin_user", key_id) is True
    assert repo.list_api_keys("pin_user")[0]["revoked_at"] is not None
    assert get_service().authenticate_api_key(raw_key) is None


def test_key_list_hides_raw_key_and_hash(
    keyed_user: tuple[PolicyRepository, Engine, str, str],
) -> None:
    repo, _, raw_key, key_id = keyed_user
    keys = repo.list_api_keys("pin_user")
    assert len(keys) == 1
    assert keys[0]["key_id"] == key_id
    assert keys[0]["key_prefix"] == api_key_prefix(raw_key)
    assert set(keys[0]) == {"key_id", "key_prefix", "revoked_at"}


def test_issue_key_requires_an_existing_user(
    keyed_user: tuple[PolicyRepository, Engine, str, str],
) -> None:
    repo, _, _, _ = keyed_user
    with pytest.raises(NotFoundError):
        repo.create_api_key("missing_user", hash_api_key("x"), "xxxxxxxx")

