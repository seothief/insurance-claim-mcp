"""Create/resume a separate Neon project and send two credentials directly to V2 secrets.

No DB URL/password/token is written to disk or stdout. Run locally as an operator, not in CI.
The state file contains only a project ID created by this script; keep it for safe resumption.
"""

import argparse
import json
import os
import re
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql

API = "https://console.neon.tech/api/v2"
PROJECT_NAME = "insurance-claim-mcp-v2"
DATABASE = "insurance_claim_v2"
APP_ROLE = "insurance_claim_v2_app"


class Neon:
    def __init__(self, token: str) -> None:
        self.token = token

    def request(self, method: str, path: str, body: dict | None = None) -> dict[str, Any]:
        request = urllib.request.Request(
            API + path,
            data=json.dumps(body).encode() if body is not None else None,
            method=method,
            headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"},
        )
        for attempt in range(6):
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    return json.load(response)
            except urllib.error.HTTPError as exc:
                # New-project operations temporarily lock the branch. Do not retry project
                # creation: ambiguous failures there could create a second project.
                if exc.code != 423 or (method == "POST" and path == "/projects") or attempt == 5:
                    raise
                time.sleep(min(2 ** (attempt + 1), 10))
        raise RuntimeError("Neon operation remained locked")


def verified_uri(raw: str) -> str:
    parts = urllib.parse.urlsplit(raw)
    if parts.scheme not in {"postgres", "postgresql"} or parts.path != "/" + DATABASE:
        raise ValueError("Unexpected V2 database URI")
    if not parts.hostname or not parts.hostname.endswith(".neon.tech"):
        raise ValueError("Expected a Neon host")
    query = dict(urllib.parse.parse_qsl(parts.query))
    # Bundled libpq/OpenSSL may not share the distro's default CA search path.
    # Pin the Debian/Ubuntu CA bundle, while keeping hostname/certificate verification enabled.
    query.update(sslmode="verify-full", sslrootcert="/etc/ssl/certs/ca-certificates.crt")
    return urllib.parse.urlunsplit(parts._replace(
        scheme="postgresql", query=urllib.parse.urlencode(query),
    ))


def store_secret(project: str, name: str, uri: str) -> str:
    if name not in {
        "insurance-claim-v2-database-url", "insurance-claim-v2-migration-database-url",
        "insurance-claim-v2-smoke-key",
    }:
        raise ValueError("Not a V2 secret")
    result = subprocess.run([
        "gcloud", "secrets", "versions", "add", name, "--project", project,
        "--data-file=-", "--format=value(name)",
    ], input=uri, text=True, capture_output=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError("Failed to store a V2 secret; output suppressed")
    version = result.stdout.strip().rsplit("/", 1)[-1]
    if not re.fullmatch(r"[1-9][0-9]*", version):
        raise RuntimeError("Unexpected secret version response")
    return version


def ensure_app_role(owner_uri: str, gcp_project: str) -> tuple[str, str]:
    """SQL-created roles do not inherit Neon's API-created neon_superuser membership."""
    with psycopg.connect(owner_uri, autocommit=True, connect_timeout=20) as connection:
        row = connection.execute(
            "SELECT oid, rolsuper, rolcreaterole, rolcreatedb, rolreplication, rolbypassrls "
            "FROM pg_roles WHERE rolname = %s", (APP_ROLE,),
        ).fetchone()
        if row is not None:
            membership = connection.execute(
                "SELECT 1 FROM pg_auth_members WHERE member = %s", (row[0],),
            ).fetchone()
            if any(row[1:]) or membership:
                raise ValueError("Existing app role is privileged; operator review required")
            result = subprocess.run([
                "gcloud", "secrets", "versions", "access", "latest", "--project", gcp_project,
                "--secret", "insurance-claim-v2-database-url",
            ], capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                raise ValueError("Existing app role requires its existing secret; no auto rotation")
            uri = verified_uri(result.stdout.strip())
            app = urllib.parse.urlsplit(uri)
            owner = urllib.parse.urlsplit(owner_uri)
            if app.hostname != owner.hostname or app.username != APP_ROLE:
                raise ValueError("Existing app secret belongs to a different database")
            return uri, store_secret(gcp_project, "insurance-claim-v2-database-url", uri)
        password = secrets.token_urlsafe(48)
        parts = urllib.parse.urlsplit(owner_uri)
        host = parts.netloc.split("@", 1)[1]
        authority = APP_ROLE + ":" + urllib.parse.quote(password, safe="") + "@" + host
        uri = urllib.parse.urlunsplit(parts._replace(netloc=authority))
        # Save before role creation: a crash can resume without resetting a live app password.
        version = store_secret(gcp_project, "insurance-claim-v2-database-url", uri)
        connection.execute(sql.SQL(
            "CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE "
            "NOREPLICATION NOBYPASSRLS",
        ).format(sql.Identifier(APP_ROLE), sql.Literal(password)))
        return uri, version


def ensure_probe_secret(project: str) -> str:
    name = "insurance-claim-v2-smoke-key"
    result = subprocess.run([
        "gcloud", "secrets", "versions", "list", name, "--project", project,
        "--filter=state:ENABLED", "--sort-by=~createTime", "--limit=1", "--format=value(name)",
    ], capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError("Cannot inspect V2 probe secret")
    version = result.stdout.strip().rsplit("/", 1)[-1]
    if version:
        if not re.fullmatch(r"[1-9][0-9]*", version):
            raise ValueError("Invalid probe secret version")
        return version
    return store_secret(project, name, "icv2_" + secrets.token_urlsafe(48))


def provision(
    api: Neon, state: Path, gcp_project: str, region: str, create: bool, org_id: str | None = None,
) -> dict:
    if org_id is not None and not re.fullmatch(r"org-[a-z0-9-]+", org_id):
        raise ValueError("Invalid Neon organization ID")
    if state.exists():
        if state.stat().st_mode & 0o077:
            raise ValueError("State file must be private")
        saved = json.loads(state.read_text())
        if saved.get("service") != PROJECT_NAME:
            raise ValueError("Invalid V2 state")
        project_id = saved["project_id"]
        if not re.fullmatch(r"[a-zA-Z0-9-]+", project_id):
            raise ValueError("Invalid project ID")
        project = api.request("GET", f"/projects/{project_id}")["project"]
        if project["name"] != PROJECT_NAME:
            raise ValueError("Project is not owned by this V2 setup")
    else:
        if not create:
            raise ValueError("First provisioning requires --create-project")
        # No paid plan/compute upgrade, branch deletion or V1 project selection is performed.
        project_config = {
            "name": PROJECT_NAME, "region_id": region, "pg_version": 17,
        }
        if org_id:
            project_config["org_id"] = org_id
        project = api.request("POST", "/projects", {"project": project_config})["project"]
        project_id = project["id"]
        # Exclusive private creation; project metadata only, never credentials.
        with open(state, "x", opener=lambda path, flags: os.open(path, flags, 0o600)) as handle:
            json.dump({"service": PROJECT_NAME, "project_id": project_id}, handle)
        print("V2 Neon project created; ID saved for safe resume")
    if not re.fullmatch(r"[a-zA-Z0-9-]+", project_id):
        raise ValueError("Invalid project ID")
    branches = api.request("GET", f"/projects/{project_id}/branches")["branches"]
    branch = next(item for item in branches if item.get("default"))
    branch_id = branch["id"]
    base = f"/projects/{project_id}/branches/{branch_id}"
    databases = api.request("GET", base + "/databases")["databases"]
    owner = next(item["owner_name"] for item in databases if item["name"] == "neondb")
    if DATABASE not in {item["name"] for item in databases}:
        api.request("POST", base + "/databases", {
            "database": {"name": DATABASE, "owner_name": owner},
        })
    query = urllib.parse.urlencode({
        "branch_id": branch_id, "database_name": DATABASE, "role_name": owner, "pooled": "false",
    })
    raw = api.request("GET", f"/projects/{project_id}/connection_uri?{query}")["uri"]
    owner_uri = verified_uri(raw)
    _app_uri, app_version = ensure_app_role(owner_uri, gcp_project)
    owner_version = store_secret(
        gcp_project, "insurance-claim-v2-migration-database-url", owner_uri,
    )
    return {
        "V2_NEON_PROJECT_ID": project_id,
        "V2_DATABASE_SECRET_VERSION": app_version,
        "V2_MIGRATION_SECRET_VERSION": owner_version,
        "V2_SMOKE_SECRET_VERSION": ensure_probe_secret(gcp_project),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--create-project", action="store_true")
    parser.add_argument("--state", type=Path, default=Path(".neon-state.json"))
    parser.add_argument("--region", default="aws-ap-southeast-1")
    args = parser.parse_args()
    try:
        token = os.environ["NEON_API_KEY"]
        gcp_project = os.environ["V2_GCP_PROJECT_ID"]
        if not token or not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", gcp_project):
            raise ValueError("Invalid operator configuration")
        result = provision(
            Neon(token), args.state, gcp_project, args.region, args.create_project,
            os.environ.get("NEON_ORG_ID"),
        )
        print(json.dumps(result))
        return 0
    except Exception:
        print("V2 Neon setup failed. Resume using the private state file; details suppressed.",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
