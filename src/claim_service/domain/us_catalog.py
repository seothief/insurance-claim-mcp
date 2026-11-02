"""US supplemental (fixed-benefit) coverage rules.

US hospital indemnity, accident and critical illness plans have no standardized wording, so no
rule here carries payable numbers. Every rule stays verified=False and is calculated only from a
rider's ``rule_config_override`` read off that policy's certificate / schedule of benefits.
``rule_config["schedule_fields"]`` documents the override keys each rule expects; it is never used
for calculation. Amounts are whole US dollars.
"""

from claim_service.domain.models import CoverageRule

US_SOURCE = "Not standardized: requires this policy's schedule of benefits (rule_config_override)"
US_BASE_DOCUMENTS = ["Insurer claim form", "Itemized bill (UB-04 / CMS-1500) with ICD-10-CM codes"]

# Order matters for keyword matching: "ICU confinement" must hit ICU before confinement.
US_RULES: tuple[CoverageRule, ...] = (
    CoverageRule(
        rule_id="US_ICU_CONFINEMENT",
        category="US_FIXED_BENEFIT",
        display_name="ICU Confinement Benefit",
        match_keywords=["icu", "intensive care", "critical care unit"],
        rule_config={"schedule_fields": {"max_days": "required: maximum payable ICU days"}},
        required_documents=["Hospital records showing ICU days"],
        source_reference=US_SOURCE,
    ),
    CoverageRule(
        rule_id="US_HOSPITAL_ADMISSION",
        category="US_FIXED_BENEFIT",
        display_name="Hospital Admission Benefit",
        match_keywords=["admission", "hospital admit"],
        rule_config={
            "schedule_fields": {
                "exclude_icd10_prefixes": "optional list of excluded ICD-10-CM prefixes",
            }
        },
        required_documents=["Hospital discharge summary (admission and discharge dates)"],
        source_reference=US_SOURCE,
    ),
    CoverageRule(
        rule_id="US_HOSPITAL_CONFINEMENT",
        category="US_FIXED_BENEFIT",
        display_name="Daily Hospital Confinement Benefit",
        match_keywords=["confinement", "daily hospital", "hospital stay", "per day"],
        rule_config={
            "schedule_fields": {
                "max_days": "required: maximum payable days per confinement",
                "elimination_days": "optional: unpaid first days (default 0)",
            }
        },
        required_documents=["Hospital discharge summary (admission and discharge dates)"],
        source_reference=US_SOURCE,
    ),
    CoverageRule(
        rule_id="US_CRITICAL_ILLNESS",
        category="US_FIXED_BENEFIT",
        display_name="Critical Illness Lump Sum",
        match_keywords=[
            "critical illness",
            "cancer",
            "heart attack",
            "stroke",
            "specified disease",
        ],
        rule_config={
            "schedule_fields": {
                "target_icd10_prefixes": "required: covered ICD-10-CM prefixes for this condition",
                "exclude_icd10_prefixes": "optional list of excluded ICD-10-CM prefixes",
                "benefit_percent": "optional: percent of the face amount paid (default 100)",
            }
        },
        required_documents=["Physician statement confirming the diagnosis and date"],
        source_reference=US_SOURCE,
    ),
    CoverageRule(
        rule_id="US_ACCIDENT_FRACTURE",
        category="US_FIXED_BENEFIT",
        display_name="Accident Fracture Benefit",
        match_keywords=["fracture", "broken bone"],
        rule_config={
            "schedule_fields": {
                "schedule": "required: ICD-10-CM prefix -> dollar amount, e.g. {\"S72\": 4000}",
            }
        },
        required_documents=["X-ray or imaging report", "Accident report or physician statement"],
        source_reference=US_SOURCE,
    ),
    CoverageRule(
        rule_id="US_EMERGENCY_ROOM",
        category="US_FIXED_BENEFIT",
        display_name="Emergency Room Benefit",
        match_keywords=["emergency room", "emergency treatment", "er visit", "er benefit"],
        rule_config={
            "schedule_fields": {
                "injury_only": "optional: true when only accident-related ER visits pay",
            }
        },
        required_documents=["Emergency room record"],
        source_reference=US_SOURCE,
    ),
)
