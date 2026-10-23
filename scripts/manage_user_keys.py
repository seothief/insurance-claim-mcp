"""Per-user API/MCP key management CLI (operator only).

Issues, lists and revokes keys that authenticate /mcp requests via the `X-User-Key` header.
Only the SHA-256 hash of a key is stored; the raw key is printed exactly once at issue time.
The operator must hand the raw key to its owner over an approved secret channel.

Examples (from the repository root):

    python scripts/manage_user_keys.py issue --user-id my_alias
    python scripts/manage_user_keys.py list --user-id my_alias
    python scripts/manage_user_keys.py revoke --user-id my_alias --key-id <key_id>
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_URL = f"sqlite:///{(PROJECT_ROOT / 'claim_service.db').as_posix()}"


def _get_repository(database_url: str):
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    from sqlalchemy import create_engine

    from claim_service.db.engine import init_schema
    from claim_service.db.repository import PolicyRepository

    engine = create_engine(database_url)
    init_schema(engine)
    return PolicyRepository(engine)


def _issue(repo, user_id: str) -> int:
    if not repo.user_exists(user_id):
        print(f"오류: 사용자를 찾을 수 없습니다: {user_id}", file=sys.stderr)
        return 1
    from claim_service.domain.security import api_key_prefix, generate_api_key, hash_api_key

    raw = generate_api_key()
    key_id = repo.create_api_key(user_id, hash_api_key(raw), api_key_prefix(raw))
    print(f"사용자 '{user_id}'에게 키를 발급했습니다 (key_id: {key_id})")
    print("새 키 (이번에만 표시; 안전한 비밀 전달 경로로 보내세요):")
    print(raw)
    print("서버에는 SHA-256 해시만 저장됩니다.")
    return 0


def _list(repo, user_id: str) -> int:
    keys = repo.list_api_keys(user_id)
    if not keys:
        print(f"사용자 '{user_id}'의 발급 키가 없습니다.")
        return 1
    print(f"사용자 '{user_id}'의 액세스 키:")
    for key in keys:
        state = "폐기됨" if key.get("revoked_at") else "사용 중"
        print(f"  key_id={key['key_id']}  prefix={key['key_prefix']}...  상태={state}")
    return 0


def _revoke(repo, user_id: str | None, key_id: str) -> int:
    ok = repo.revoke_api_key(user_id, key_id) if user_id else False
    if not ok:
        print(
            f"오류: 키를 폐기할 수 없습니다 ({key_id}). user_id와 key_id를 확인하세요.",
            file=sys.stderr,
        )
        return 1
    print(f"키를 폐기했습니다: {key_id}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL),
        help="SQLAlchemy database URL (default: local SQLite at project root)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    issue = subparsers.add_parser("issue", help="issue a new key and print it once")
    issue.add_argument("--user-id", required=True)
    listing = subparsers.add_parser("list", help="list issued keys (no raw keys)")
    listing.add_argument("--user-id", required=True)
    revoke = subparsers.add_parser("revoke", help="revoke a key")
    revoke.add_argument("--user-id")
    revoke.add_argument("--key-id", required=True)
    args = parser.parse_args()

    try:
        repo = _get_repository(args.database_url)
    except Exception as exc:  # pragma: no cover - depends on local DB availability
        print(f"데이터베이스 연결에 실패했습니다: {exc}", file=sys.stderr)
        return 1

    if args.command == "issue":
        return _issue(repo, args.user_id)
    if args.command == "list":
        return _list(repo, args.user_id)
    if args.command == "revoke":
        return _revoke(repo, args.user_id, args.key_id)
    return 1


if __name__ == "__main__":
    sys.exit(main())
