"""Helpers for using Google Cloud CLI's locally stored ADC without displaying tokens."""

from __future__ import annotations

import os
import subprocess


def _gcloud_command(*args: str) -> list[str]:
    if os.name == "nt":
        return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", "gcloud.cmd", *args]
    return ["gcloud", *args]


def get_adc_access_token() -> str:
    """Return a refreshed ADC access token, keeping CLI output and errors private."""
    try:
        result = subprocess.run(
            _gcloud_command("auth", "application-default", "print-access-token"),
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(
            "Google Cloud CLI를 실행할 수 없습니다. 설치 후 새 터미널을 열어 주세요."
        ) from exc

    token = result.stdout.strip()
    if result.returncode != 0 or not token:
        raise RuntimeError(
            "Google ADC 인증이 없거나 만료되었습니다. "
            "`gcloud auth application-default login`을 실행해 주세요."
        )
    return token