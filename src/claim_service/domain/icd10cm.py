"""ICD-10-CM (US clinical modification) code normalization and prefix matching.

ICD-10-CM codes are a letter, a digit, then up to five alphanumeric characters, optionally
written with a dot after the third character: ``S72.001A`` (fracture of femur, initial
encounter). Codes are normalized to the dot-less upper-case form (``S72001A``) so a bill
written either way matches the same benefit-schedule prefix.

Which codes a benefit covers always comes from the policy certificate, never from here.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

CODE_PATTERN = re.compile(r"^[A-Z]\d[0-9A-Z]{0,5}$")
# Schedule prefixes may be a whole chapter letter (``C`` = neoplasms) or any longer stem.
PREFIX_PATTERN = re.compile(r"^[A-Z][0-9A-Z]{0,6}$")


def normalize_icd10(raw: str) -> str:
    """``s72.001a`` -> ``S72001A``. Raises ValueError on an invalid shape."""
    code = raw.strip().replace(" ", "").replace(".", "").upper()
    if not CODE_PATTERN.match(code):
        raise ValueError(f"Not an ICD-10-CM code: {raw!r}")
    return code


def _normalize_prefix(raw: str) -> str | None:
    prefix = raw.strip().replace(" ", "").replace(".", "").upper()
    return prefix if PREFIX_PATTERN.match(prefix) else None


def _normalized_prefixes(prefixes: Sequence[str]) -> list[str]:
    return [p for p in (_normalize_prefix(str(raw)) for raw in prefixes) if p]


def match_icd10(
    code: str | None, prefixes: Sequence[str], excluded: Sequence[str] | None = None
) -> bool:
    """True when ``code`` starts with an included prefix and with no excluded prefix."""
    if not code:
        return False
    try:
        normalized = normalize_icd10(code)
    except ValueError:
        return False
    if any(normalized.startswith(ex) for ex in _normalized_prefixes(excluded or [])):
        return False
    return any(normalized.startswith(prefix) for prefix in _normalized_prefixes(prefixes))


def schedule_amount(code: str | None, schedule: Mapping[str, object]) -> tuple[str, int] | None:
    """Return ``(prefix, amount)`` for the longest schedule prefix that ``code`` starts with."""
    if not code:
        return None
    try:
        normalized = normalize_icd10(code)
    except ValueError:
        return None
    best: tuple[str, int] | None = None
    for raw_prefix, amount in schedule.items():
        prefix = _normalize_prefix(raw_prefix)
        if prefix is None:
            continue
        if normalized.startswith(prefix) and (best is None or len(prefix) > len(best[0])):
            best = (prefix, int(str(amount)))
    return best
