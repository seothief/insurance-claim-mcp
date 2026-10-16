"""Read-only check for the known synthetic sample user; never prints other user data."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gcloud_auth import get_adc_access_token  # noqa: E402
from gcp_secrets import get_database_url  # noqa: E402

from claim_service.db.engine import create_db_engine  # noqa: E402

SAMPLE_USER_ID = "user_123"


def main() -> int:
    try:
        token = get_adc_access_token()
        database_url = get_database_url(token)
        engine = create_db_engine(database_url)
        try:
            with engine.connect() as connection:
                counts: dict[str, int] = {}
                for table in (
                    "coverage_rules",
                    "users",
                    "user_policies",
                    "user_policy_riders",
                ):
                    counts[table] = int(
                        connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
                    )

                user: Any = connection.execute(
                    text("SELECT display_alias FROM users WHERE user_id = :user_id"),
                    {"user_id": SAMPLE_USER_ID},
                ).mappings().first()
                policies = connection.execute(
                    text(
                        "SELECT company, product_name, source_type FROM user_policies "
                        "WHERE user_id = :user_id"
                    ),
                    {"user_id": SAMPLE_USER_ID},
                ).mappings().all()
                riders = connection.execute(
                    text(
                        "SELECT r.source_type, r.rider_name FROM user_policy_riders AS r "
                        "JOIN user_policies AS p ON p.policy_id = r.policy_id "
                        "WHERE p.user_id = :user_id"
                    ),
                    {"user_id": SAMPLE_USER_ID},
                ).mappings().all()

                marked_user = user is not None and user["display_alias"] == "샘플 사용자"
                marked_policies = bool(policies) and all(
                    policy["company"].startswith("샘플보험사")
                    and policy["product_name"].startswith("샘플 ")
                    and policy["source_type"] == "SYNTHETIC_SAMPLE"
                    for policy in policies
                )
                marked_riders = all(
                    rider["source_type"] == "SYNTHETIC_SAMPLE"
                    and "(샘플)" in rider["rider_name"]
                    for rider in riders
                )

                print("읽기 전용 운영 데이터 검토 완료 (개인별 세부정보 미출력)")
                for table, count in counts.items():
                    print(f"{table}={count}")
                print(f"SAMPLE_USER_PRESENT={user is not None}")
                print(f"SAMPLE_ALIAS_MARKER_MATCH={marked_user}")
                print(f"SAMPLE_POLICY_COUNT={len(policies)}")
                print(f"SAMPLE_POLICIES_MARKED_SYNTHETIC={marked_policies}")
                print(f"SAMPLE_RIDER_COUNT={len(riders)}")
                print(f"SAMPLE_RIDERS_MARKED_SYNTHETIC={marked_riders}")
        finally:
            engine.dispose()
    except (RuntimeError, httpx.HTTPError, KeyError, ValueError, OSError):
        print(
            "운영 데이터 검토에 실패했습니다. 인증, Secret Manager 권한, "
            "네트워크 접근을 확인하세요. 상세 응답과 비밀 값은 숨겼습니다.",
            file=sys.stderr,
        )
        return 1
    except Exception:
        print(
            "운영 데이터 검토 중 DB 오류가 발생했습니다. "
            "세부 오류와 데이터는 출력하지 않았습니다.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())