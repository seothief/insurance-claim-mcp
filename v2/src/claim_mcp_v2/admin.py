"""Local/operator-only bootstrap. Never expose this command as an MCP tool."""

import argparse
import json
import secrets
import sys
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine, insert, select, update

from claim_mcp_v2.config import Settings
from claim_mcp_v2.db import actors, build_engine, check_ready, credentials, memberships, workspaces
from claim_mcp_v2.security import key_hash

PROBE_WORKSPACE_ID = "00000000-0000-4000-8000-000000000001"
PROBE_ACTOR_ID = "00000000-0000-4000-8000-000000000002"
PROBE_MEMBERSHIP_ID = "00000000-0000-4000-8000-000000000003"
PROBE_KEY_ID = "00000000-0000-4000-8000-000000000004"


def ensure_probe(engine: Engine, raw: str) -> None:
    """Seed only a synthetic, context-only identity; never output the raw release probe key."""
    if not raw.startswith("icv2_") or not 40 <= len(raw) <= 200:
        raise ValueError("Invalid V2 probe credential")
    with engine.begin() as conn:
        row = conn.execute(select(credentials).where(
            credentials.c.key_id == PROBE_KEY_ID,
        )).mappings().first()
        if row is not None:
            if row["key_hash"] != key_hash(raw) or row["membership_id"] != PROBE_MEMBERSHIP_ID:
                raise ValueError("Probe key rotation requires an explicit operator procedure")
            conn.execute(update(credentials).where(credentials.c.key_id == PROBE_KEY_ID).values(
                expires_at=datetime.now(UTC) + timedelta(days=90),
            ))
            return
        conn.execute(insert(workspaces).values(
            workspace_id=PROBE_WORKSPACE_ID, display_name="system-probe", active=True,
        ))
        conn.execute(insert(actors).values(
            actor_id=PROBE_ACTOR_ID, display_name="system-probe", active=True,
        ))
        conn.execute(insert(memberships).values(
            membership_id=PROBE_MEMBERSHIP_ID, actor_id=PROBE_ACTOR_ID,
            workspace_id=PROBE_WORKSPACE_ID, active=True,
        ))
        conn.execute(insert(credentials).values(
            key_id=PROBE_KEY_ID, membership_id=PROBE_MEMBERSHIP_ID, key_hash=key_hash(raw),
            expires_at=datetime.now(UTC) + timedelta(days=90),
        ))


def bootstrap(
    engine: Engine, workspace_name: str, actor_name: str, expires_days: int = 30,
) -> dict[str, str]:
    if not 1 <= expires_days <= 90:
        raise ValueError("Credential lifetime must be between 1 and 90 days")
    if not 1 <= len(workspace_name) <= 100 or not 1 <= len(actor_name) <= 100:
        raise ValueError("Names must be between 1 and 100 characters")
    ids = {name: str(uuid.uuid4()) for name in [
        "workspace_id", "actor_id", "membership_id", "key_id",
    ]}
    raw = "icv2_" + secrets.token_urlsafe(48)
    with engine.begin() as conn:
        conn.execute(insert(workspaces).values(
            workspace_id=ids["workspace_id"], display_name=workspace_name, active=True,
        ))
        conn.execute(insert(actors).values(
            actor_id=ids["actor_id"], display_name=actor_name, active=True,
        ))
        conn.execute(insert(memberships).values(
            membership_id=ids["membership_id"], actor_id=ids["actor_id"],
            workspace_id=ids["workspace_id"], active=True,
        ))
        conn.execute(insert(credentials).values(
            key_id=ids["key_id"], membership_id=ids["membership_id"], key_hash=key_hash(raw),
            expires_at=datetime.now(UTC) + timedelta(days=expires_days),
        ))
    return {**ids, "api_key": raw}


def main() -> int:
    parser = argparse.ArgumentParser(description="V2 operator-only credential management")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("bootstrap")
    create.add_argument("--workspace-name", required=True)
    create.add_argument("--actor-name", required=True)
    create.add_argument("--expires-days", type=int, default=30)
    revoke = sub.add_parser("revoke")
    revoke.add_argument("--key-id", required=True)
    args = parser.parse_args()
    engine = None
    try:
        settings = Settings()
        engine = build_engine(settings)
        check_ready(engine, settings.database_project_id)
        if args.command == "bootstrap":
            # Raw credential is printed exactly once. Do not run in cloud jobs or CI logs.
            print(json.dumps(bootstrap(
                engine, args.workspace_name, args.actor_name, args.expires_days,
            )))
        else:
            with engine.begin() as conn:
                conn.execute(update(credentials).where(credentials.c.key_id == args.key_id).values(
                    revoked_at=datetime.now(UTC),
                ))
            print("V2 key revocation completed")
        return 0
    except Exception:
        print("V2 administration failed; no configuration details logged", file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
