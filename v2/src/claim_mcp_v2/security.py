"""Expiring, workspace-bound credentials, revalidated on every MCP request."""

import hashlib
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Engine, select

from claim_mcp_v2.db import actors, credentials, memberships, utc_datetime, workspaces


@dataclass(frozen=True)
class Identity:
    actor_id: str
    workspace_id: str
    membership_id: str
    key_id: str


current_identity: ContextVar[Identity | None] = ContextVar("v2_identity", default=None)


def key_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def authenticate(engine: Engine, raw: str) -> Identity | None:
    if not raw.startswith("icv2_") or len(raw) > 200:
        return None
    query = (
        select(credentials, memberships.c.actor_id, memberships.c.workspace_id)
        .join(memberships, credentials.c.membership_id == memberships.c.membership_id)
        .join(actors, memberships.c.actor_id == actors.c.actor_id)
        .join(workspaces, memberships.c.workspace_id == workspaces.c.workspace_id)
        .where(
            credentials.c.key_hash == key_hash(raw), credentials.c.revoked_at.is_(None),
            memberships.c.active.is_(True), actors.c.active.is_(True),
            workspaces.c.active.is_(True),
        )
    )
    with engine.connect() as conn:
        row = conn.execute(query).mappings().first()
    if row is None or utc_datetime(row["expires_at"]) <= datetime.now(UTC):
        return None
    return Identity(
        actor_id=row["actor_id"], workspace_id=row["workspace_id"],
        membership_id=row["membership_id"], key_id=row["key_id"],
    )
