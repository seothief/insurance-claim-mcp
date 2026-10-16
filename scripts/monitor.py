"""Live monitor for the Cloud Run service logs and Neon PostgreSQL database state.

Usage:
    .\\.venv\\Scripts\\python.exe scripts/monitor.py           # 1회 조회
    .\\.venv\\Scripts\\python.exe scripts/monitor.py --watch   # 5초마다 실시간 갱신
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text

# Allow direct execution from a source checkout without an editable install.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gcloud_auth import get_adc_access_token  # noqa: E402
from gcp_secrets import PROJECT_ID, get_database_url  # noqa: E402

from claim_service.db.engine import create_db_engine  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SERVICE_NAME = "insurance-claim-mcp"

def _print_db_status(db_url: str) -> None:
    print("=== [1] Neon PostgreSQL DB 현황 ===")
    engine = create_db_engine(db_url)
    with engine.connect() as conn:
        for table in ("coverage_rules", "users", "user_policies", "user_policy_riders"):
            count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            print(f"  - {table}: {count}건")

        print("\n=== [2] 등록된 사용자 및 보험 요약 ===")
        users = conn.execute(
            text(
                "SELECT user_id, display_alias, (pin_hash IS NOT NULL) AS pin_set, created_at "
                "FROM users ORDER BY created_at DESC"
            )
        ).mappings()
        for u in users:
            uid = u["user_id"]
            policies = conn.execute(
                text(
                    "SELECT company, product_name, policy_type, silson_generation, enrolled_year "
                    "FROM user_policies WHERE user_id = :uid"
                ),
                {"uid": uid},
            ).mappings()
            pol_list = [f"{p['company']} {p['product_name']}({p['policy_type']})" for p in policies]
            print(
                f"  - user_id={uid} (별칭={u['display_alias']}, PIN보호={u['pin_set']}, "
                f"가입보험={len(pol_list)}건): {', '.join(pol_list) or '없음'}"
            )


def _print_cloud_run_logs(token: str, limit: int = 12) -> None:
    print(f"\n=== [3] Cloud Run 최근 로그 ({SERVICE_NAME}, 최신 {limit}건) ===")
    resp = httpx.post(
        "https://logging.googleapis.com/v2/entries:list",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "resourceNames": [f"projects/{PROJECT_ID}"],
            "filter": (
                'resource.type="cloud_run_revision" '
                f'AND resource.labels.service_name="{SERVICE_NAME}"'
            ),
            "orderBy": "timestamp desc",
            "pageSize": limit,
        },
        timeout=15.0,
    )
    resp.raise_for_status()
    entries: list[dict[str, Any]] = resp.json().get("entries", [])
    for entry in entries:
        ts = entry.get("timestamp", "")[:19].replace("T", " ")
        http_req = entry.get("httpRequest")
        if http_req:
            method = http_req.get("requestMethod", "")
            status = http_req.get("status", "")
            url = http_req.get("requestUrl", "")
            latency = http_req.get("latency", "")
            print(f"  [{ts} UTC] HTTP {status} {method} {url} ({latency})")
        else:
            payload = str(entry.get("textPayload", "")).strip().splitlines()
            first_line = payload[0][:100] if payload else "(empty)"
            print(f"  [{ts} UTC] APP  {first_line}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor Cloud Run logs and Neon DB state.")
    parser.add_argument("--watch", action="store_true", help="Refresh every 5 seconds.")
    parser.add_argument("--interval", type=int, default=5, help="Refresh interval in seconds.")
    args = parser.parse_args()

    try:
        token = get_adc_access_token()
        db_url = get_database_url(token)
    except (RuntimeError, httpx.HTTPError) as exc:
        print(f"Google Cloud 인증 또는 Secret Manager 조회 실패: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
    while True:
        if args.watch:
            print("\n" + "=" * 72)
        _print_db_status(db_url)
        _print_cloud_run_logs(token)
        if not args.watch:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()

