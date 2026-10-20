"""Standard coverage rules seeded into the database.

All values are NOT verified against policy text yet (verified=False). Change verified only after
confirming the source document. Rules without confirmed numbers keep an empty rule_config so the
evaluator reports them as not evaluated instead of guessing.
"""

import re
from collections.abc import Iterable

from claim_service.domain.models import CoverageRule

UNVERIFIED_SOURCE = "미확보: 약관 원문 대조 전 (PoC 수치 또는 일반 명칭 기반 초안)"
UNCONFIGURED_SILSON_SOURCE = "미확보: 약관 수치 미입력 (계산하지 않음, 원문 확보 후 입력)"
BURN_KCD_PREFIXES = [f"T{n}" for n in range(20, 33)]

SILSON_DOCUMENTS = ["진료비 계산서·영수증 (병원 원무과 발급)"]

SILSON_RULES: tuple[CoverageRule, ...] = (
    CoverageRule(
        rule_id="SILSON_GEN1",
        category="INDEMNITY_SILSON",
        display_name="1세대 실손의료비",
        rule_config={},
        required_documents=SILSON_DOCUMENTS,
        source_reference=UNCONFIGURED_SILSON_SOURCE,
    ),
    CoverageRule(
        rule_id="SILSON_GEN2",
        category="INDEMNITY_SILSON",
        display_name="2세대 실손의료비",
        rule_config={},
        required_documents=SILSON_DOCUMENTS,
        source_reference=UNCONFIGURED_SILSON_SOURCE,
    ),
    CoverageRule(
        rule_id="SILSON_GEN3",
        category="INDEMNITY_SILSON",
        display_name="3세대 실손의료비",
        rule_config={},
        required_documents=SILSON_DOCUMENTS,
        source_reference=UNCONFIGURED_SILSON_SOURCE,
    ),
    CoverageRule(
        rule_id="SILSON_GEN4",
        category="INDEMNITY_SILSON",
        display_name="4세대 실손의료비",
        rule_config={
            "outpatient_deductible": {"clinic": 10000, "hospital": 15000, "general": 20000},
            "outpatient_covered_deductible_ratio": 0.2,
            "outpatient_uncovered_deductible_min": 30000,
            "outpatient_uncovered_deductible_ratio": 0.3,
            "inpatient_covered_ratio": 0.8,
            "inpatient_uncovered_ratio": 0.7,
        },
        required_documents=[
            *SILSON_DOCUMENTS,
            "진료비 세부내역서 (급여/비급여 분리)",
        ],
        source_reference=UNVERIFIED_SOURCE,
    ),
)


FIXED_RULES: tuple[CoverageRule, ...] = (
    CoverageRule(
        rule_id="FRACTURE_DIAGNOSIS",
        category="FIXED_BENEFIT",
        display_name="골절진단비",
        match_keywords=["골절진단", "fracture", "broken bone", "骨折"],
        rule_config={
            "target_kcd_prefixes": [
                "S02",
                "S12",
                "S22",
                "S32",
                "S42",
                "S52",
                "S62",
                "S72",
                "S82",
                "S92",
            ],
            "exclusion_kcd": ["S02.5"],
        },
        required_documents=["방사선(X-ray) 판독결과지 또는 골절 진단서 (KCD 코드 기재)"],
        source_reference=UNVERIFIED_SOURCE,
    ),
    CoverageRule(
        rule_id="CAST_TREATMENT",
        category="FIXED_BENEFIT",
        display_name="깁스치료비 (통깁스)",
        match_keywords=["깁스", "cast treatment", "plaster cast", "orthopedic cast", "ギプス"],
        rule_config={
            "target_edi_codes": ["T6020", "T6030"],
            "exclusion_keywords": ["부목", "반깁스", "splint", "T6010", "シーネ"],
        },
        required_documents=["의무기록 사본 또는 진단서 (석고붕대 시술 사실 명기)"],
        source_reference=UNVERIFIED_SOURCE,
    ),
    CoverageRule(
        rule_id="FLU_ANTIVIRAL",
        category="FIXED_BENEFIT",
        display_name="독감(인플루엔자) 치료비",
        match_keywords=["독감", "인플루엔자", "influenza", "flu antiviral", "インフルエンザ"],
        rule_config={
            "target_kcd_prefixes": ["J09", "J10", "J11"],
            "antiviral_drugs": [
                "타미플루",
                "페라미플루",
                "오셀타미비르",
                "코미플루",
                "tamiflu",
                "oseltamivir",
                "xofluza",
                "baloxavir",
                "relenza",
                "peramivir",
                "rapivab",
                "タミフル",
                "ゾフルーザ",
                "イナビル",
            ],
        },
        required_documents=["처방전(환자보관용) 또는 약국 영수증 (항바이러스제명 기재)"],
        source_reference=UNVERIFIED_SOURCE,
    ),
    CoverageRule(
        rule_id="DISEASE_SURGERY",
        category="FIXED_BENEFIT",
        display_name="질병수술비",
        match_keywords=[
            "질병수술",
            "illness surgery",
            "sickness surgery",
            "disease surgery",
            "surgical benefit",
            "疾病手術",
            "手術給付金",
        ],
        rule_config={
            "target_keywords": [
                "절제",
                "절단",
                "용종제거",
                "시술/수술",
                "resection",
                "excision",
                "polypectomy",
                "appendectomy",
                "cholecystectomy",
                "surgery",
                "切除",
                "摘出",
                "手術",
            ]
        },
        required_documents=["수술확인서 (수술명, 수술일자, 질병분류코드 기재)"],
        source_reference=UNVERIFIED_SOURCE,
    ),
    CoverageRule(
        rule_id="INJURY_SURGERY",
        category="FIXED_BENEFIT",
        display_name="상해수술비",
        match_keywords=["상해수술", "accident surgery", "injury surgery", "傷害手術"],
        rule_config={},
        required_documents=["수술확인서 (수술명, 수술일자, 상해 경위 기재)"],
        source_reference=UNVERIFIED_SOURCE,
    ),
)

EXTRA_FIXED_RULES: tuple[CoverageRule, ...] = (
    CoverageRule(
        rule_id="BURN_DIAGNOSIS",
        category="FIXED_BENEFIT",
        display_name="화상진단비",
        match_keywords=["화상", "burn", "火傷", "熱傷"],
        rule_config={"target_kcd_prefixes": BURN_KCD_PREFIXES},
        required_documents=["진단서 또는 진료확인서 (화상 KCD 코드 T20~T32 기재)"],
        source_reference=UNVERIFIED_SOURCE,
    ),
    CoverageRule(
        rule_id="WOUND_SUTURE",
        category="FIXED_BENEFIT",
        display_name="창상봉합술 치료비",
        match_keywords=[
            "창상",
            "봉합",
            "suture",
            "laceration",
            "stitches",
            "wound repair",
            "創傷",
            "縫合",
        ],
        rule_config={
            "target_keywords": ["봉합", "suture", "laceration repair", "stitches", "縫合"]
        },
        required_documents=["진료비 세부내역서 (창상봉합술 처치 항목 기재)"],
        source_reference=UNVERIFIED_SOURCE,
    ),
    CoverageRule(
        rule_id="INPATIENT_DAILY",
        category="FIXED_BENEFIT",
        display_name="입원일당",
        match_keywords=[
            "입원일당",
            "입원일수",
            "hospital indemnity",
            "daily hospital",
            "hospital confinement",
            "inpatient daily",
            "入院日額",
            "入院給付金",
        ],
        rule_config={},
        required_documents=["입퇴원확인서 (입원일수 기재)"],
        source_reference=UNVERIFIED_SOURCE,
    ),
    CoverageRule(
        rule_id="EMERGENCY_ROOM_VISIT",
        category="FIXED_BENEFIT",
        display_name="응급실 내원진료비",
        match_keywords=["응급실", "emergency room", "er visit", "emergency visit", "救急外来"],
        rule_config={},
        required_documents=["응급실 진료기록 (내원 경위 및 응급 여부 기재)"],
        source_reference=UNVERIFIED_SOURCE,
    ),
)

STANDARD_RULES = (*SILSON_RULES, *FIXED_RULES, *EXTRA_FIXED_RULES)


def _bigrams(text: str) -> set[str]:
    cleaned = re.sub(r"[^0-9A-Za-z가-힣]", "", text)
    return {cleaned[i : i + 2] for i in range(len(cleaned) - 1)}


def match_fixed_rule(rider_name: str, rules: Iterable[CoverageRule]) -> str | None:
    """Map a raw rider name from a policy document to a standard FIXED_BENEFIT rule id."""
    lowered = rider_name.lower()
    for rule in rules:
        if rule.category == "FIXED_BENEFIT" and any(
            keyword.lower() in lowered for keyword in rule.match_keywords
        ):
            return rule.rule_id
    return None


def candidate_rule_ids(rider_name: str, rules: Iterable[CoverageRule]) -> list[str]:
    """Fixed-benefit rules sharing a two-character word with the rider name, for AI confirmation."""
    rider_words = _bigrams(rider_name)
    return [
        rule.rule_id
        for rule in rules
        if rule.category == "FIXED_BENEFIT" and _bigrams(rule.display_name) & rider_words
    ]
