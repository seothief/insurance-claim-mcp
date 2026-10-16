"""Safely add a new shared API_KEY version to Google Secret Manager.

Dry-run is the default. Applying a rotation interrupts every client still using the old key.
"""

from __future__ import annotations

import argparse
import base64
import secrets
import sys
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gcloud_auth import get_adc_access_token  # noqa: E402

PROJECT_ID = "project-93d02748-0cbc-4596-902"
SECRET_ID = "API_KEY"
API_ROOT = "https://secretmanager.googleapis.com/v1"


def _request(
    method: str, url: str, token: str, *, json: dict[str, Any] | None = None
) -> httpx.Response:
    response = httpx.request(
        method,
        url,
        headers={"Authorization": f"Bearer {token}"},
        json=json,
        timeout=20.0,
    )
    response.raise_for_status()
    return response


def _enabled_versions(token: str, project: str, secret: str) -> list[str]:
    url = f"{API_ROOT}/projects/{project}/secrets/{secret}/versions?pageSize=100"
    versions: list[str] = []
    while url:
        result = _request("GET", url, token).json()
        versions.extend(
            str(item["name"].rsplit("/", maxsplit=1)[-1])
            for item in result.get("versions", [])
            if item.get("state") == "ENABLED"
        )
        next_page = result.get("nextPageToken")
        url = (
            f"{API_ROOT}/projects/{project}/secrets/{secret}/versions"
            f"?pageSize=100&pageToken={next_page}"
            if next_page
            else ""
        )
    return versions


def rotate(project: str, secret: str, apply: bool) -> int:
    """Inspect current enabled versions and optionally append a freshly generated version."""
    token = get_adc_access_token()
    versions = _enabled_versions(token, project, secret)
    print(f"Secret: {secret}; 활성 버전 수: {len(versions)}")
    if versions:
        print(f"활성 버전 번호: {', '.join(versions)}")
    if not apply:
        print("DRY RUN: 변경 없음. 실제 추가는 --apply와 확인 문구 입력이 필요합니다.")
        return 0

    confirmation = input(
        "모든 클라이언트의 키를 바꿉니다. 계속하려면 ROTATE를 입력하세요: "
    ).strip()
    if confirmation != "ROTATE":
        print("취소됨: Secret Manager를 변경하지 않았습니다.")
        return 1

    new_key = secrets.token_urlsafe(48)
    parent = f"projects/{project}/secrets/{secret}"
    payload = base64.b64encode(new_key.encode("ascii")).decode("ascii")
    result = _request(
        "POST",
        f"{API_ROOT}/{parent}:addVersion",
        token,
        json={"payload": {"data": payload}},
    ).json()
    version = str(result.get("name", "")).rsplit("/", maxsplit=1)[-1]
    if not version:
        print("오류: 새 버전이 추가됐지만 버전 번호를 확인할 수 없습니다.", file=sys.stderr)
        return 1
    print(f"새 Secret Manager 버전을 추가했습니다: {version}")
    print("새 키 (이번에만 표시; 안전한 비밀 전달 경로로 전달하세요):")
    print(new_key)
    print("모든 클라이언트의 공용 키 설정을 갱신하세요.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=PROJECT_ID, help="Google Cloud project ID")
    parser.add_argument("--secret", default=SECRET_ID, help="Secret Manager secret ID")
    parser.add_argument(
        "--apply", action="store_true", help="Add a version after explicit confirmation"
    )
    args = parser.parse_args()
    try:
        return rotate(args.project, args.secret, args.apply)
    except (RuntimeError, httpx.HTTPError, KeyError, ValueError, OSError):
        print(
            "API 키 회전에 실패했습니다. ADC 인증, Secret Manager 권한과 네트워크를 확인하세요. "
            "비밀 값과 상세 응답은 표시하지 않았습니다.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())