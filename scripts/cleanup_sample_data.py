"""Preview or remove only the exact hard-coded synthetic seed records for user_123."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy import Engine, create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gcloud_auth import get_adc_access_token  # noqa: E402
from gcp_secrets import get_database_url  # noqa: E402

USER_ID = "user_123"
SAMPLE_ALIAS = "샘플 사용자"
SAMPLE_POLICIES = (
    ("샘플보험사A", "샘플 실손의료비보험(4세대)"),
    ("샘플보험사B", "샘플 종합보험"),
)
SAMPLE_RIDERS = ("골절진단비(샘플)", "깁스치료비(샘플)")


def _get_engine() -> Engine:
    database_url = get_database_url(get_adc_access_token())
    return create_engine(database_url, pool_pre_ping=True)


def _get_sample_policies(connection: object) -> list[dict[str, object]]:
    rows = connection.execute(  # type: ignore[attr-defined]
        text(
            "SELECT policy_id, company, product_name, source_type FROM user_policies "
            "WHERE user_id = :user_id AND "
            "((company = :company_a AND product_name = :product_a) OR "
            "(company = :company_b AND product_name = :product_b))"
        ),
        {
            "user_id": USER_ID,
            "company_a": SAMPLE_POLICIES[0][0],
            "product_a": SAMPLE_POLICIES[0][1],
            "company_b": SAMPLE_POLICIES[1][0],
            "product_b": SAMPLE_POLICIES[1][1],
        },
    ).mappings().all()
    return [dict(row) for row in rows]


def _remaining_summary(connection: object) -> tuple[int, Counter[str], int]:
    policies = connection.execute(  # type: ignore[attr-defined]
        text(
            "SELECT source_type, COUNT(*) AS amount FROM user_policies "
            "WHERE user_id = :user_id GROUP BY source_type"
        ),
        {"user_id": USER_ID},
    ).mappings().all()
    policy_count = sum(int(row["amount"]) for row in policies)
    sources = Counter({str(row["source_type"]): int(row["amount"]) for row in policies})
    rider_count = int(
        connection.execute(  # type: ignore[attr-defined]
            text(
                "SELECT COUNT(*) FROM user_policy_riders r JOIN user_policies p "
                "ON p.policy_id = r.policy_id WHERE p.user_id = :user_id"
            ),
            {"user_id": USER_ID},
        ).scalar_one()
    )
    return policy_count, sources, rider_count


def _run(delete: bool) -> int:
    engine = _get_engine()
    try:
        with engine.begin() if delete else engine.connect() as connection:
            user = connection.execute(
                text("SELECT display_alias FROM users WHERE user_id = :user_id"),
                {"user_id": USER_ID},
            ).mappings().first()
            policies = _get_sample_policies(connection)

            candidate_ids = [str(policy["policy_id"]) for policy in policies]
            seed_rider_rows = []
            other_rider_count = 0
            for policy_id in candidate_ids:
                policy_riders = connection.execute(
                    text(
                        "SELECT rider_id, rider_name FROM user_policy_riders "
                        "WHERE policy_id = :policy_id"
                    ),
                    {"policy_id": policy_id},
                ).mappings().all()
                seed_rider_rows.extend(
                    row for row in policy_riders if row["rider_name"] in SAMPLE_RIDERS
                )
                other_rider_count += sum(
                    row["rider_name"] not in SAMPLE_RIDERS for row in policy_riders
                )

            print(f"SAMPLE_ACCOUNT_PRESENT={user is not None}")
            print(
                "SAMPLE_ALIAS_MARKER_MATCH="
                f"{user is not None and user['display_alias'] == SAMPLE_ALIAS}"
            )
            print(f"EXACT_SEED_POLICIES_MATCHED={len(policies)}")
            print(f"EXACT_SEED_RIDERS_MATCHED={len(seed_rider_rows)}")
            print(f"OTHER_RIDERS_TO_PRESERVE={other_rider_count}")

            if delete:
                if policies and (user is None or user["display_alias"] != SAMPLE_ALIAS):
                    raise RuntimeError("Sample account marker changed; refusing deletion.")
                if seed_rider_rows:
                    connection.execute(
                        text("DELETE FROM user_policy_riders WHERE rider_id = ANY(:ids)"),
                        {"ids": [str(row["rider_id"]) for row in seed_rider_rows]},
                    )

                deleted_policies = 0
                for policy_id in candidate_ids:
                    remaining_riders = int(
                        connection.execute(
                            text(
                                "SELECT COUNT(*) FROM user_policy_riders "
                                "WHERE policy_id = :policy_id"
                            ),
                            {"policy_id": policy_id},
                        ).scalar_one()
                    )
                    if remaining_riders == 0:
                        connection.execute(
                            text(
                                "DELETE FROM user_policies WHERE policy_id = :policy_id "
                                "AND user_id = :user_id"
                            ),
                            {"policy_id": policy_id, "user_id": USER_ID},
                        )
                        deleted_policies += 1

                cleared_alias = False
                if user is not None and user["display_alias"] == SAMPLE_ALIAS:
                    result = connection.execute(
                        text(
                            "UPDATE users SET display_alias = NULL WHERE user_id = :user_id "
                            "AND display_alias = :sample_alias"
                        ),
                        {"user_id": USER_ID, "sample_alias": SAMPLE_ALIAS},
                    )
                    cleared_alias = result.rowcount > 0

                print(f"DELETED_SEED_RIDERS={len(seed_rider_rows)}")
                print(f"DELETED_SEED_POLICIES={deleted_policies}")
                print(f"CLEARED_SAMPLE_ALIAS={cleared_alias}")
                print("SAMPLE_ACCOUNT_ID_PRESERVED=True")

            remaining_policy_count, source_counts, remaining_riders = _remaining_summary(
                connection
            )
            print(f"REMAINING_POLICY_COUNT={remaining_policy_count}")
            print(f"REMAINING_RIDER_COUNT={remaining_riders}")
            print(
                "REMAINING_POLICY_SOURCE_COUNTS="
                + (
                    ",".join(
                        f"{key}:{value}" for key, value in sorted(source_counts.items())
                    )
                    or "none"
                )
            )
        return 0
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete exact seeded records only; preserve all other user_123 data.",
    )
    args = parser.parse_args()
    try:
        return _run(args.delete)
    except Exception:
        print(
            "샘플 데이터 처리 실패. 상세 오류와 개인 데이터는 표시하지 않았습니다.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())