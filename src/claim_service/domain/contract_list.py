"""Parse an insurance contract list (e.g. the Korea Life Insurance Association inquiry printout).

The printout only lists contracts: company, product name, status, relation and period. It has no
riders and no coverage amounts, so nothing here fabricates them. Parsing is pure and does no I/O.
"""

import re
from dataclasses import dataclass
from typing import Literal

from claim_service.domain.models import PolicyType

ContractStatus = Literal["ACTIVE", "EXPIRED", "TERMINATED", "DORMANT", "LAPSED", "UNKNOWN"]
ProductCategory = Literal[
    "SILSON", "COMPREHENSIVE", "DRIVER", "AUTO", "TRAVEL", "LIFE", "GROUP", "OTHER"
]
ImportAction = Literal["REGISTER", "SKIP_INACTIVE", "SKIP_NOT_CLAIMABLE", "NEEDS_REVIEW"]

STATUS_LABELS: tuple[tuple[str, ContractStatus], ...] = (
    ("유지", "ACTIVE"),
    ("소멸", "TERMINATED"),
    ("해약", "TERMINATED"),
    ("만기", "EXPIRED"),
    ("휴면", "DORMANT"),
    ("실효", "LAPSED"),
)
ROW_PATTERN = re.compile(
    r"^(?P<prefix>.*?)\s+(?P<policy_no>[0-9A-Za-z][0-9A-Za-z*\-]{5,})\s+"
    r"(?P<status>\S+)\s+(?P<relation>보험계약자|피보험자|수익자)\s+"
    r"(?P<start>\d{4}-\d{2}-\d{2})\s+(?P<end>\d{4}-\d{2}-\d{2})\b"
)
COMPANY_SUFFIXES = ("화재", "손해보험", "생명", "라이프", "해상", "보험")
ROW_TYPE_MARKER = "보험계약"

# Product-name keywords. Order matters: the first matching rule wins.
CATEGORY_RULES: tuple[tuple[ProductCategory, tuple[str, ...]], ...] = (
    ("AUTO", ("자동차", "애니카", "이륜차")),
    ("TRAVEL", ("여행",)),
    ("SILSON", ("실손", "의료비")),
    ("DRIVER", ("운전자",)),
    ("GROUP", ("단체",)),
    ("LIFE", ("종신", "정기보험", "연금", "저축", "CI보험")),
    ("COMPREHENSIVE", ("종합", "통합", "패밀리", "라이더")),
)
CATEGORY_TO_POLICY_TYPE: dict[ProductCategory, PolicyType] = {
    "SILSON": "SILSON",
    "COMPREHENSIVE": "COMPREHENSIVE",
    "DRIVER": "DRIVER",
    "LIFE": "FIXED_BENEFIT",
    "GROUP": "OTHER",
    "AUTO": "OTHER",
    "TRAVEL": "OTHER",
    "OTHER": "OTHER",
}
# Categories whose benefits are not paid from hospital receipts by this service.
NOT_CLAIMABLE: frozenset[ProductCategory] = frozenset({"AUTO", "TRAVEL"})


@dataclass(frozen=True)
class ContractRow:
    company: str
    product_name: str
    status: ContractStatus
    relation: str
    start_date: str
    end_date: str
    category: ProductCategory
    policy_no_masked: str


@dataclass(frozen=True)
class ImportDecision:
    row: ContractRow
    action: ImportAction
    reason: str




def _looks_like_company(line: str) -> bool:
    """A company header is a short line without digits that ends with a company-type suffix."""
    text = line.strip()
    if not text or len(text) > 20 or re.search(r"\d", text) or " " in text:
        return False
    return any(text.endswith(suffix) for suffix in COMPANY_SUFFIXES)


def _split_company_and_product(prefix: str, current_company: str) -> tuple[str, str]:
    """Split the text before the policy number into (company, product).

    Rows are printed as '<company> 보험계약 <product>' on the first row of a company group and as
    '보험계약 <product>' on following rows, where the company comes from the group header.
    """
    text = prefix.strip()
    if text.startswith(ROW_TYPE_MARKER):
        return current_company, text.removeprefix(ROW_TYPE_MARKER).strip()
    head, marker, rest = text.partition(f" {ROW_TYPE_MARKER} ")
    if marker:
        return head.strip(), rest.strip()
    # The first row of a group may not carry the marker: '<company> <product>'.
    company, _, product = text.partition(" ")
    return company.strip(), product.strip()


def parse_contract_list(text: str) -> list[ContractRow]:
    """Parse extracted printout text into rows. Lines that do not look like a row are skipped."""
    rows: list[ContractRow] = []
    current_company = ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = ROW_PATTERN.match(line)
        if match is None:
            if _looks_like_company(line):
                current_company = line
            continue
        company, product = _split_company_and_product(match.group("prefix"), current_company)
        if company:
            current_company = company
        rows.append(
            ContractRow(
                company=company or current_company,
                product_name=product,
                status=parse_status(match.group("status")),
                relation=match.group("relation"),
                start_date=match.group("start"),
                end_date=match.group("end"),
                category=classify_product(product),
                policy_no_masked=match.group("policy_no"),
            )
        )
    return rows


def decide_import(row: ContractRow) -> ImportDecision:
    """Decide what to do with one contract. Nothing is registered without this decision."""
    if row.status != "ACTIVE":
        return ImportDecision(row, "SKIP_INACTIVE", f"계약 상태가 {row.status}이라 제외합니다.")
    if row.category in NOT_CLAIMABLE:
        return ImportDecision(
            row,
            "SKIP_NOT_CLAIMABLE",
            "자동차/여행 보험은 병원 영수증 청구 대상이 아니라 제외합니다.",
        )
    if row.category == "OTHER":
        return ImportDecision(
            row, "NEEDS_REVIEW", "상품 종류를 상품명으로 판단할 수 없어 사용자 확인이 필요합니다."
        )
    return ImportDecision(row, "REGISTER", "유효한 계약이라 등록합니다 (특약은 별도 입력 필요).")


def decide_all(rows: list[ContractRow]) -> list[ImportDecision]:
    return [decide_import(row) for row in rows]


def to_policy_type(category: ProductCategory) -> PolicyType:
    return CATEGORY_TO_POLICY_TYPE[category]


def enrolled_year(row: ContractRow) -> int | None:
    match = re.match(r"(\d{4})-", row.start_date)
    return int(match.group(1)) if match else None

def classify_product(product_name: str) -> ProductCategory:
    """Classify by product-name keywords. Unknown names fall back to OTHER, never a guess."""
    for category, keywords in CATEGORY_RULES:
        if any(keyword in product_name for keyword in keywords):
            return category
    return "OTHER"


def parse_status(label: str) -> ContractStatus:
    """Map a printed status label (e.g. '유지(정상)', '소멸(해약포함)') to a status."""
    for keyword, status in STATUS_LABELS:
        if label.startswith(keyword):
            return status
    return "UNKNOWN"
