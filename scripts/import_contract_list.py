"""Import a contract list PDF (e.g. the Korea Life Insurance Association printout) locally.

The PDF stays on this PC. Only company, product name, policy type and year are sent, and only with
--register. Without it the script prints what it would do (dry run). No riders or amounts are
read because the printout does not contain them.

Usage:
    .\\.venv\\Scripts\\python.exe scripts/import_contract_list.py <file.pdf>
    .\\.venv\\Scripts\\python.exe scripts/import_contract_list.py <file.pdf> --register `
        --user-id <id> --pin <pin> --base-url https://... --api-key <key>
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import httpx
from pypdf import PdfReader

from claim_service.domain.contract_list import (
    ImportDecision,
    decide_all,
    enrolled_year,
    parse_contract_list,
    to_policy_type,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
logging.getLogger("pypdf").setLevel(logging.CRITICAL)

ACTION_LABELS = {
    "REGISTER": "등록",
    "SKIP_INACTIVE": "제외(유효하지 않음)",
    "SKIP_NOT_CLAIMABLE": "제외(청구 대상 아님)",
    "NEEDS_REVIEW": "확인 필요",
}


def read_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        raise SystemExit("암호화된 PDF는 읽지 않습니다.")
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def build_report(decisions: list[ImportDecision]) -> str:
    counts: dict[str, int] = {}
    for decision in decisions:
        counts[decision.action] = counts.get(decision.action, 0) + 1
    lines = [f"읽은 계약 {len(decisions)}건"]
    for action, label in ACTION_LABELS.items():
        lines.append(f"  - {label}: {counts.get(action, 0)}건")
    lines.append("")
    for decision in decisions:
        row = decision.row
        lines.append(
            f"[{ACTION_LABELS[decision.action]}] {row.company} / {row.product_name} "
            f"({row.category}, {row.status}, {row.start_date}~{row.end_date})"
        )
    return "\n".join(lines)


def register(decisions: list[ImportDecision], args: argparse.Namespace) -> None:
    headers = {"X-API-Key": args.api_key} if args.api_key else {}
    base = args.base_url.rstrip("/")
    params = {"pin": args.pin} if args.pin else None
    created = updated = 0
    for decision in decisions:
        if decision.action != "REGISTER":
            continue
        row = decision.row
        body = {
            "company": row.company,
            "product_name": row.product_name,
            "policy_type": to_policy_type(row.category),
            "enrolled_year": enrolled_year(row),
            "riders": [],
        }
        response = httpx.post(
            f"{base}/api/users/{args.user_id}/policies",
            json=body,
            headers=headers,
            params=params,
            timeout=30.0,
        )
        response.raise_for_status()
        if response.json().get("action") == "CREATED":
            created += 1
        else:
            updated += 1
    print(f"\n등록 완료: 신규 {created}건, 갱신 {updated}건")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a contract list PDF (dry run by default).")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--output", type=Path, help="Also write the report to this UTF-8 file.")
    parser.add_argument("--register", action="store_true", help="Actually send to the service.")
    parser.add_argument("--user-id")
    parser.add_argument("--pin")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--api-key", default="")
    args = parser.parse_args()

    if not args.pdf.is_file():
        raise SystemExit(f"파일을 찾을 수 없습니다: {args.pdf}")
    rows = parse_contract_list(read_pdf_text(args.pdf))
    decisions = decide_all(rows)
    report = build_report(decisions)
    print(report)
    if args.output:
        args.output.write_text(report, encoding="utf-8")
    if not args.register:
        print("\n(드라이런입니다. 서버에 아무것도 보내지 않았습니다. 등록하려면 --register)")
        return
    if not (args.user_id and args.base_url):
        raise SystemExit("--register에는 --user-id와 --base-url이 필요합니다.")
    register(decisions, args)


if __name__ == "__main__":
    main()
