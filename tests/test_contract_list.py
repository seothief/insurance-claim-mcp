"""Contract list parsing and import decisions, using synthetic rows in the printout format."""

from claim_service.domain.contract_list import (
    classify_product,
    decide_all,
    decide_import,
    enrolled_year,
    parse_contract_list,
    parse_status,
    to_policy_type,
)

SAMPLE = """보험가입내역 조회결과
보험회사 구분 상품명 증권(계좌) 번호 보험계약 상태 보험계약 관계 보험기간
가나생명 보험계약 가나종신보험(해약환급금 일부지급형 00********* 유지(정상) 보험계약자 2023-02-27 9999-12-31 가나판매 02********
다라화재 보험계약 Readycar개인용자동차보험 71*************** 유지(정상) 보험계약자 2026-07-19 2027-07-19 충청GA 1566-7711
마바손해보험 보험계약 (무)테스트 종합보험(20.06)(2종_해지환 20********* 유지(정상) 보험계약자 2020-07-22 2083-07-22 수도고객 02********
사아화재
보험계약 365연간 해외여행보험 82************ 유지(정상) 보험계약자 2025-10-03 2026-10-03 다이렉트 1577-3339
보험계약 무배당 사아화재 운전자보험 안전운전 파트너(1 51************ 유지(정상) 보험계약자 2018-06-29 2038-06-29 충청.GA2센 02-6925-1730
보험계약 무배당 사아화재 통합보험 수퍼플러스(1202) 51************ 유지(정상) 보험계약자 2012-03-09 2084-03-09 충청.GA2센 02-6925-1730
보험계약 애니카다이렉트_개인용 124P04******** 만기 보험계약자 2024-07-19 2025-07-19 다이렉트 1577-3339
보험계약 애니카다이렉트_개인용 124P04******** 소멸(해약포함) 보험계약자 2024-07-19 2025-07-19 다이렉트 1577-3339
자차화재 보험계약 (무)새단체보장공제Ⅰ 36*********** 휴면 피보험자 2005-08-08 2006-08-08 대전영업부 042-221-5549
카타보험 보험계약 알 수 없는 상품 99********** 유지(정상) 보험계약자 2021-01-01 2031-01-01 영업점 02********
안내사항
상기 조회결과는 접수일 현재 기준이며 세부내역은 해당회사에 직접 문의하시기 바랍니다.
"""


def test_parse_reads_every_contract_row() -> None:
    rows = parse_contract_list(SAMPLE)
    assert len(rows) == 10


def test_group_header_company_applies_to_following_rows() -> None:
    rows = parse_contract_list(SAMPLE)
    companies = {row.product_name: row.company for row in rows}
    assert companies["무배당 사아화재 통합보험 수퍼플러스(1202)"] == "사아화재"
    assert companies["365연간 해외여행보험"] == "사아화재"


def test_first_row_carries_its_own_company() -> None:
    rows = parse_contract_list(SAMPLE)
    first = rows[0]
    assert first.company == "가나생명"
    assert first.product_name.startswith("가나종신보험")
    assert first.status == "ACTIVE"
    assert first.start_date == "2023-02-27"


def test_status_labels_are_mapped() -> None:
    assert parse_status("유지(정상)") == "ACTIVE"
    assert parse_status("만기") == "EXPIRED"
    assert parse_status("소멸(해약포함)") == "TERMINATED"
    assert parse_status("휴면") == "DORMANT"
    assert parse_status("실효") == "LAPSED"
    assert parse_status("처음 보는 상태") == "UNKNOWN"


def test_product_classification_by_name() -> None:
    assert classify_product("Readycar개인용자동차보험") == "AUTO"
    assert classify_product("애니카 다이렉트_이륜차") == "AUTO"
    assert classify_product("365연간 해외여행보험") == "TRAVEL"
    assert classify_product("무배당 사아화재 운전자보험 안전운전 파트너") == "DRIVER"
    assert classify_product("무배당 사아화재 통합보험 수퍼플러스(1202)") == "COMPREHENSIVE"
    assert classify_product("참좋은훼밀리플러스+종합보험2007") == "COMPREHENSIVE"
    assert classify_product("가나종신보험") == "LIFE"
    assert classify_product("알 수 없는 상품") == "OTHER"


def test_only_active_claimable_contracts_are_registered() -> None:
    decisions = {d.row.product_name: d for d in decide_all(parse_contract_list(SAMPLE))}
    assert decisions["무배당 사아화재 통합보험 수퍼플러스(1202)"].action == "REGISTER"
    assert decisions["무배당 사아화재 운전자보험 안전운전 파트너(1"].action == "REGISTER"
    assert decisions["Readycar개인용자동차보험"].action == "SKIP_NOT_CLAIMABLE"
    assert decisions["365연간 해외여행보험"].action == "SKIP_NOT_CLAIMABLE"


def test_inactive_contracts_are_skipped_even_when_claimable() -> None:
    rows = parse_contract_list(SAMPLE)
    inactive = [r for r in rows if r.status in {"EXPIRED", "TERMINATED", "DORMANT"}]
    assert len(inactive) == 3
    assert all(decide_import(r).action == "SKIP_INACTIVE" for r in inactive)


def test_unknown_product_needs_review_instead_of_guessing() -> None:
    rows = parse_contract_list(SAMPLE)
    unknown = next(r for r in rows if r.product_name == "알 수 없는 상품")
    assert decide_import(unknown).action == "NEEDS_REVIEW"


def test_policy_type_and_year_helpers() -> None:
    rows = parse_contract_list(SAMPLE)
    comp = next(r for r in rows if "수퍼플러스" in r.product_name)
    assert to_policy_type(comp.category) == "COMPREHENSIVE"
    assert enrolled_year(comp) == 2012


def test_text_without_rows_returns_nothing() -> None:
    assert parse_contract_list("조회 된 내역이 없습니다.\n안내사항") == []
