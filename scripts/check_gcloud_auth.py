"""Check Google Cloud CLI and ADC authentication without exposing account or token data."""

from __future__ import annotations

import json
import subprocess
import sys

from gcloud_auth import _gcloud_command, get_adc_access_token


def _run_gcloud(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        _gcloud_command(*args),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )


def main() -> int:
    try:
        accounts = _run_gcloud("auth", "list", "--filter=status:ACTIVE", "--format=json")
        if accounts.returncode != 0:
            print("gcloud CLI 인증 상태를 확인할 수 없습니다.")
            return 1
        account_data = json.loads(accounts.stdout)
        if not any(account.get("status") == "ACTIVE" for account in account_data):
            print("gcloud CLI 로그인 없음: `gcloud auth login`을 실행하세요.")
            return 1

        project = _run_gcloud("config", "get-value", "project")
        project_id = project.stdout.strip()
        if project.returncode != 0 or not project_id or project_id == "(unset)":
            print(
                "기본 프로젝트가 설정되지 않았습니다. "
                "`gcloud config set project <PROJECT_ID>`를 실행하세요."
            )
            return 1

        get_adc_access_token()
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"gcloud CLI 확인 실패: {exc}")
        return 1
    except RuntimeError as exc:
        print(str(exc))
        return 1

    print("gcloud CLI 로그인: 정상")
    print("기본 프로젝트: 설정됨 (값은 보안상 표시하지 않음)")
    print("Application Default Credentials: 정상, 토큰 자동 갱신 가능")
    print("계정 이메일·토큰·시크릿 값은 출력하지 않았습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())