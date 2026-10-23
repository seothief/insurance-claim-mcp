"""KCD (한국표준질병·사인분류) code parsing and validation helpers.

KCD codes follow the ICD-10 family layout: a single leading letter (A..Z) followed
by digits, optionally with 1 or 2 decimal places for finer Korean breakdowns.
Examples: ``A00`` (3rd-level), ``S72.0`` (4th-level), ``S72.00`` (5th-level, Korean).

These helpers work on the *official* ``kcd_codes`` master loaded from the public
classification table (Statistics Korea / KOICD) or the HIRA disease-diagnosis master
(sangbyeong master). The master is the shared vocabulary; which codes a coverage rule
covers is decided by each policy's riders (user_policy_riders), never by this module.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence

CODE_PATTERN = re.compile(r"^[A-Z](\d{2}(\.\d{1,2})?)?$")


def normalize_code(raw: str) -> str:
    """Strip whitespace and uppercase a KCD code. Raises ValueError on invalid shape."""
    code = raw.strip().replace("-", "").upper()
    if not CODE_PATTERN.match(code):
        raise ValueError(f"KCD 코드 형식이 아닙니다: {raw!r}")
    return code


def classify_code(code: str) -> tuple[str, int]:
    """Return ``(category_letter, level)`` for a normalized code.

    Level meanings (KCD): 1=대분류(장), 3=소분류(3단), 4=세분류(4단), 5=세세분류(5단).
    A two-digit code without a dot (e.g. ``S72``) is the 3rd level; ``S72.0`` and
    ``S72.00`` are the 4th and 5th levels. Level 2 (중분류) is a group/block label
    (e.g. ``S70-S79``) so it never appears as a single stored code.
    """
    normalized = normalize_code(code)
    category = normalized[0]
    digits = normalized[1:].split(".", 1)[0]
    if not digits:
        level = 1
    elif len(digits) <= 2 and "." not in normalized[1:]:
        level = 3
    elif "." in normalized[1:]:
        decimals = normalized[1:].split(".", 1)[1]
        level = 4 if len(decimals) == 1 else 5
    else:
        # e.g. exactly three digits with no dot are not expected in KCD layout.
        level = 3
    return category, level


def code_exists(code: str, codes: Mapping[str, object]) -> bool:
    """True when the normalized code is present in the loaded KCD master."""
    return normalize_code(code) in codes


def missing_prefixes(
    prefixes: Sequence[str], codes: Mapping[str, object]
) -> list[str]:
    """Return prefixes that match no actual KCD code in the master.

    A prefix is valid when some stored code starts with it (e.g. ``S72`` matches
    ``S72.0``). This is used to verify hardcoded rule configs against the official table.
    """
    normalized: list[str] = []
    for prefix in prefixes:
        try:
            normalized.append(normalize_code(prefix))
        except ValueError:
            normalized.append(prefix)
    missing: list[str] = []
    for prefix in normalized:
        if not any(stored.startswith(prefix) for stored in codes):
            missing.append(prefix)
    return missing


def codes_for_prefix(
    prefix: str, codes: Iterable[Mapping[str, object]]
) -> list[Mapping[str, object]]:
    """Return master rows whose code starts with the given prefix (inclusive)."""
    normalized = normalize_code(prefix)
    return [row for row in codes if str(row["code"]).startswith(normalized)]