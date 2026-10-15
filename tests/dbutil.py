"""Test helper: pick the database URL for one test (temp SQLite, or TEST_DATABASE_URL in CI)."""

import os
from pathlib import Path


def database_url_for(tmp_path: Path, name: str) -> str:
    """Return the shared external DB URL when TEST_DATABASE_URL is set, else a temp SQLite file."""
    external = os.environ.get("TEST_DATABASE_URL")
    if external:
        return external
    return f"sqlite:///{(tmp_path / name).as_posix()}"
