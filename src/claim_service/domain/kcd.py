"""KCD (한국표준질병·사인분류) code parsing and validation helpers.

The HIRA disease-diagnosis master (상병마스터) uses dot-less codes whose digit count
encodes the breakdown level: ``S72`` (3rd), ``S720`` (4th), ``S7200`` (5th). Codes with a
dot (the official KCD notation, e.g. ``S72.0``) are accepted as input and normalized to
the same dot-less line format so lookups are consistent regardless of input style.

Level meanings (KCD): 1=대분류(장), 3=소분류(3단), 4=세분류(4단), 5=세세분류(5단).
Level 2 (중분류) is a group/block label (e.g. ``S70-S79``) and never appears as a code.

This module is the shared vocabulary only; which codes a coverage rule covers is decided
by each policy's riders (user_policy_riders), never here.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence

# A..Z bare (대분류) or a letter followed by 2-5 digits (3rd/4th/5th level).
CODE_PATTERN = re.compile(r"^[A-Z](\d{2,5})?$")


def normalize_code(raw: str) -> str:
    """Normalize to the dot-less line format. Raises ValueError on invalid shape.

    ``S72.0`` -> ``S720``, ``A00.00`` -> ``A0000``, ``s72`` -> ``S72``.
    """
    code = raw.strip().replace(" ", "").replace("-", "").upper().replace(".", "")
    if not CODE_PATTERN.match(code):
        raise ValueError(f"KCD 코드 형식이 아닙니다: {raw!r}")
    return code


def classify_code(code: str) -> tuple[str, int]:
    """Return ``(category_letter, level)`` for a normalized code."""
    normalized = normalize_code(code)
    category = normalized[0]
    num_digits = len(normalized) - 1
    if num_digits == 0:
        level = 1  # 대분류(장)
    elif num_digits <= 2:
        level = 3  # 소분류(3단)
    elif num_digits == 3:
        level = 4  # 세분류(4단)
    else:
        level = 5  # 세세분류(5단) 및 한국 특수/한방 확장 코드
    return category, level


def code_exists(code: str, codes: Mapping[str, object]) -> bool:
    """True when the normalized code is present in the loaded KCD master."""
    return normalize_code(code) in codes


def missing_prefixes(
    prefixes: Sequence[str], codes: Mapping[str, object]
) -> list[str]:
    """Return prefixes that match no actual KCD code in the master.

    A prefix is valid when some stored code starts with it (e.g. ``S72`` matches
    ``S720``). This is used to verify hardcoded rule configs against the official table.
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
def match_kcd_code(
    kcd_code: str | None,
    prefixes: Sequence[str],
    excluded: Sequence[str] | None = None,
) -> bool:
    """True when ``kcd_code`` falls inside the given prefix ranges and is not excluded.

    Both dot-less (``S720``) and dotted (``S72.0``) inputs are normalized first, so a
    receipt written either way matches the same coverage rule. Exclusions take priority:
    a code that starts with an excluded prefix never matches, even when it also starts
    with an included prefix (e.g. ``S02.5`` 치아파절 excluded from 골절 ``S02``).

    Invalid codes simply do not match (no exception is raised).
    """
    if not kcd_code:
        return False
    try:
        normalized = normalize_code(kcd_code)
    except ValueError:
        return False
    for raw in excluded or []:
        try:
            if normalized.startswith(normalize_code(raw)):
                return False
        except ValueError:
            continue
    for raw in prefixes:
        try:
            if normalized.startswith(normalize_code(raw)):
                return True
        except ValueError:
            continue
    return False