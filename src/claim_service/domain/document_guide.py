"""Which documents to request from the insurer, by contract type.

Only a policy certificate (보험증권) counts as a calculation source. Reports or analysis
summaries that are not issued by the insurer are excluded on purpose. No I/O happens here.
"""

from typing import Literal

PolicyKind = Literal["SILSON", "COMPREHENSIVE", "DRIVER", "FIXED_BENEFIT", "LIFE", "OTHER"]

COMMON_REQUESTS: tuple[str, ...] = (
    "A. 보험증권(가입증서): 담보(특약)별 가입금액, 보험기간, 갱신형 여부, 피보험자가 적힌 것",
    "B. 특별조건, 부담보, 감액 내용이 있으면 그 부분 (증권에 적힌 특별조건 또는 특별약관)",
    "C. 가입 당시 적용된 보통약관과 특별약관 (해당 계약의 버전)",
)

KIND_REQUESTS: dict[PolicyKind, tuple[str, ...]] = {
    "SILSON": (
        "D. 실손의료보험: 가입 세대, 자기부담 비율, 갱신 정보가 적힌 증권",
    ),
    "COMPREHENSIVE": (
        "종합보험은 골절, 깁스, 수술, 입원 등 담보가 여러 개이므로 "
        "담보별 금액이 빠짐없이 적힌 증권이 필요합니다.",
    ),
    "DRIVER": (
        "운전자보험은 의료 관련 담보(입원, 수술, 진단비)가 있는지 증권에서 먼저 확인하세요.",
    ),
    "FIXED_BENEFIT": ("정액 담보(진단비, 수술비 등)의 가입금액이 적힌 증권이 필요합니다.",),
    "LIFE": (
        "생명보험은 입원, 수술, 진단 특약이 있는지 증권에서 확인하세요. "
        "없으면 계산 대상이 아닙니다.",
    ),
    "OTHER": ("상품 종류를 알 수 없으면 증권의 상품명을 먼저 확인하세요.",),
}

REQUEST_MESSAGE = (
    "제 계약(상품명: {product})의 ① 담보별 가입금액이 표시된 보험증권과 ② 가입 당시 적용된 "
    "보통약관·특별약관을 발급해 주세요. 특별조건(부담보, 감액)이 있으면 함께 표시해 주세요."
)


def request_guide(kind: PolicyKind, product_name: str) -> dict[str, object]:
    return {
        "product_name": product_name,
        "kind": kind,
        "documents_to_request": [*COMMON_REQUESTS, *KIND_REQUESTS.get(kind, ())],
        "request_message": REQUEST_MESSAGE.format(product=product_name),
        "where_to_request": [
            (
                "한국신용정보원 본인신용정보 열람서비스(credit4u.or.kr) > 보험신용정보 > "
                "정액형·실손형보험 > 상세내역 발급"
            ),
            "보험사 공식 앱",
            "보험사 공식 홈페이지의 본인 로그인 메뉴",
            "보험사 고객센터(전화, 채팅)",
            "보험사가 제공하는 우편, 이메일, 팩스, 지점 발급",
        ],
        "not_accepted": [
            "정보를 가공한 리포트나 분석 결과",
            "제3자 앱이나 조회 사이트에서 만든 요약",
            "사용자가 말로만 한 내용",
        ],
    }
