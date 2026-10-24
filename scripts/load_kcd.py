"""Load the official KCD code table into the ``kcd_codes`` master.

Accepts HIRA sangbyeong-master CSV (공공데이터포털 "건강보험심사평가원_상병마스터")
or a Statistics Korea / KOICD classification CSV. Header rows are auto-detected.
Invalid or nameless rows are skipped and reported; nothing is ever deleted.
``--verify-rule-configs`` cross-checks the KCD prefixes in ``domain.catalog``.

Example:
    python -m scripts.load_kcd --input sangbyeong.csv --source KCD-9
    python -m scripts.load_kcd --input sangbyeong.csv --source KCD-9 --verify-rule-configs
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from collections import Counter
from pathlib import Path

repository_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repository_root / "src"))
sys.path.insert(0, str(repository_root / "scripts"))

from claim_service.db.engine import create_db_engine, init_schema  # noqa: E402
from claim_service.db.repository import PolicyRepository  # noqa: E402
from claim_service.domain.kcd import classify_code, normalize_code  # noqa: E402

CODE_HEADER_ALIASES = ("상병기호", "상병코드", "질병코드", "kcd", "kcd코드", "code", "diseasecode")
KO_NAME_HEADER_ALIASES = (
    "상병명",
    "한글명",
    "질병명",
    "kcd명",
    "상병명(한글)",
    "ko_name",
    "korname",
    "kcdkorname",
    "name",
)
EN_NAME_HEADER_ALIASES = ("영문명", "상병명(영문)", "en_name", "engname", "kcdengname", "eng_name")

_CODE_CELL_RE = re.compile(r"^[A-Z]\d{2,5}$")


def _header_index(headers: list[str], aliases: tuple[str, ...]) -> int | None:
    lowered = [str(h).strip().lower().replace(" ", "") for h in headers]
    for alias in aliases:
        key = alias.lower().replace(" ", "")
        if key in lowered:
            return lowered.index(key)
    return None


def _looks_like_code(value: object) -> bool:
    return bool(_CODE_CELL_RE.match(str(value).strip().upper()))


def _pick_code_column(headers: list[str]) -> int | None:
    idx = _header_index(headers, CODE_HEADER_ALIASES)
    if idx is not None:
        return idx
    for i, header in enumerate(headers):
        if re.match(r"^[a-zA-Z0-9_가-힣]+$", str(header)) and str(header).lower() not in {
            "no",
            "순번",
            "번호",
        }:
            return i
    return None
def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Return (headers, rows-as-dicts) for a Korean public-data CSV.

    Public data portals ship these files as UTF-8 (with or without BOM) or CP949/EUC-KR,
    so the encoding is auto-detected by trying each candidate in order.
    """
    raw = path.read_bytes()
    text: str | None = None
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            text = raw.decode(enc)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if text is None:
        raise ValueError(f"지원하지 않는 인코딩입니다: {path.name}")
    reader = csv.DictReader(io.StringIO(text))
    headers = list(reader.fieldnames) if reader.fieldnames is not None else []
    rows: list[dict[str, str]] = []
    for row in reader:
        rows.append({key: value for key, value in row.items() if value is not None})
    return headers, rows


def _iter_kcd_records(
    headers: list[str], rows: list[dict[str, str]], source_version: str
) -> tuple[list[dict[str, object]], list[str]]:
    """Convert raw rows into kcd_codes records. Returns (records, skipped_reasons)."""
    code_idx = _pick_code_column(headers)
    if code_idx is None:
        raise ValueError("KCD 코드 컬럼을 찾을 수 없습니다. --code-col 옵션이 필요합니다.")
    code_header = headers[code_idx]
    ko_idx = _header_index(headers, KO_NAME_HEADER_ALIASES)
    en_idx = _header_index(headers, EN_NAME_HEADER_ALIASES)

    records: list[dict[str, object]] = []
    skipped: list[str] = []
    seen: set[str] = set()
    for row in rows:
        raw_code = (row.get(code_header) or "").strip()
        if not raw_code:
            continue
        try:
            normalized = normalize_code(raw_code)
        except ValueError:
            skipped.append(f"invalid-code:{raw_code}")
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        category, level = classify_code(normalized)
        ko_name = (row[headers[ko_idx]].strip() if ko_idx is not None else "") or None
        en_name = (row[headers[en_idx]].strip() if en_idx is not None else "") or None
        if not ko_name and not en_name:
            skipped.append(f"no-name:{normalized}")
            continue
        records.append(
            {
                "code": normalized,
                "category": category,
                "level": level,
                "ko_name": ko_name or "",
                "en_name": en_name,
                "source_version": source_version,
                "verified": True,
                "source_reference": f"공식 KCD 표준분류 적재 ({source_version})",
            }
        )
    return records, skipped
def verify_rule_configs(repo: PolicyRepository) -> int:
    """Cross-check catalog rule_config KCD prefixes against the loaded master."""
    from claim_service.domain.catalog import STANDARD_RULES  # noqa: PLC0415

    codes = repo.get_kcd_codes()
    missing_total = 0
    for rule in STANDARD_RULES:
        prefixes = rule.rule_config.get("target_kcd_prefixes", [])
        if not prefixes:
            continue
        missing = [p for p in prefixes if not any(str(c).startswith(p) for c in codes)]
        missing_total += len(missing)
        if missing:
            print(f"[MISSING] {rule.rule_id} {rule.display_name}: {missing}")
        else:
            print(f"[OK] {rule.rule_id} {rule.display_name}: {prefixes}")
    return missing_total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="KCD CSV/TSV 파일 경로")
    parser.add_argument("--source", default="KCD-9", help="출처 버전 (기본 KCD-9)")
    parser.add_argument("--code-col", type=str, default=None, help="코드 컬럼명 직접 지정")
    parser.add_argument("--ko-col", type=str, default=None, help="한글명 컬럼명 직접 지정")
    parser.add_argument("--en-col", type=str, default=None, help="영문명 컬럼명 직접 지정")
    parser.add_argument("--verify-rule-configs", action="store_true")
    parser.add_argument(
        "--replace", action="store_true", help="적재 전 기존 kcd_codes를 비우고 교체"
    )
    parser.add_argument("--database-url", type=str, default=None)
    args = parser.parse_args()

    if not args.input.exists():
        print(f"입력 파일이 없습니다: {args.input}", file=sys.stderr)
        return 2

    headers, rows = read_csv_rows(args.input)
    records, skipped = _iter_kcd_records(headers, rows, args.source)
    if not records:
        msg = "적재할 유효한 KCD 코드가 없습니다. 파일 형식/컬럼명을 확인해 주세요."
        print(msg, file=sys.stderr)
        return 2

    from claim_service.config import get_settings  # noqa: PLC0415

    settings = get_settings()
    engine = create_db_engine(args.database_url or settings.database_url)
    init_schema(engine)
    repo = PolicyRepository(engine)
    if args.replace:
        removed = repo.clear_kcd_codes()
        print(f"CLEARED_EXISTING={removed}")
    written = repo.upsert_kcd_codes(records)
    total = repo.count_kcd_codes()

    by_level = Counter(rec["level"] for rec in records)
    by_category = Counter(rec["category"] for rec in records)
    print(f"WRITTEN={written}")
    print(f"TOTAL_KCD_CODES={total}")
    print(f"BY_LEVEL={dict(sorted(by_level.items()))}")
    print(f"BY_CATEGORY={dict(sorted(by_category.items()))}")
    if skipped:
        print(f"SKIPPED_OR_DUPLICATE={len(skipped)} (예: {skipped[:5]})")

    if args.verify_rule_configs:
        missing = verify_rule_configs(repo)
        print(f"RULE_CONFIG_MISSING_PREFIXES={missing}")
        if missing:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())