"""
Insurance Claim Matching MCP Server
Personalized AI Agent to match medical documents (KCD, receipts) against user insurance policies.
"""

import json
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field
from fastmcp import FastMCP

# Initialize FastMCP Server
mcp = FastMCP("Personal-Insurance-Claim-Agent")

DATA_FILE = Path(__file__).parent / "sample_user_data.json"


def load_user_db():
    if not DATA_FILE.exists():
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@mcp.tool()
def get_user_policies(user_id: str) -> dict:
    """
    사용자가 가입한 모든 활성 보험 상품과 세부 특약(담보) 목록을 조회합니다.
    
    Args:
        user_id: 사용자 식별자 (예: 'user_123')
    """
    db = load_user_db()
    user_info = db.get(user_id)
    if not user_info:
        return {"error": f"사용자 '{user_id}'의 보험 가입 정보를 찾을 수 없습니다."}
    return user_info


@mcp.tool()
def evaluate_claim(
    user_id: str,
    kcd_code: Optional[str] = None,
    treatment_name: Optional[str] = None,
    treatment_code: Optional[str] = None,
    cost_covered: int = 0,
    cost_uncovered: int = 0,
    hospital_type: str = "clinic",
    is_inpatient: bool = False,
    prescribed_drugs: Optional[List[str]] = None
) -> dict:
    """
    약봉투, 처방전, 진료비 영수증에서 추출된 의료 데이터를 바탕으로
    가입 보험 약관을 대조하여 보장 가능 특약, 예상 수령액, 주의사항을 정밀 분석합니다.

    Args:
        user_id: 사용자 식별자
        kcd_code: 질병분류코드 (예: 'S93.4', 'S82.1', 'J10.1', 'D12.6')
        treatment_name: 처치/수술 명칭 (예: '반깁스', '통깁스', '용종 절제술')
        treatment_code: 건강보험 EDI 처치코드 (예: 'T6010' 부목, 'T6020' 석고붕대)
        cost_covered: 진료비 영수증 상 '급여 본인부담금' (원)
        cost_uncovered: 진료비 영수증 상 '비급여' 총액 (원)
        hospital_type: 병원 규모 ('clinic': 동네의원, 'hospital': 일반병원, 'general': 종합병원)
        is_inpatient: 입원 여부 (True: 입원, False: 통원)
        prescribed_drugs: 처방받은 약품 목록 (예: ['타미플루', '소염진통제'])
    """
    db = load_user_db()
    user = db.get(user_id)
    if not user:
        return {"error": f"사용자 '{user_id}'의 정보를 찾을 수 없습니다."}

    prescribed_drugs = prescribed_drugs or []
    matched_benefits = []
    total_estimated_payout = 0
    kcd_upper = (kcd_code or "").upper().strip()

    # 1. 정액 보장 보험(종합보험) 특약 대조
    for policy in user.get("policies", []):
        if policy.get("category") == "정액보장보험":
            for rider in policy.get("riders", []):
                rider_name = rider["rider_name"]
                amount = rider["amount"]

                # A. 골절진단비 검증
                if "골절" in rider_name:
                    target_prefixes = rider.get("target_kcd_prefixes", [])
                    exclusions = rider.get("exclusion_kcd", [])
                    
                    is_excluded = any(kcd_upper.startswith(ex) for ex in exclusions)
                    is_matched = any(kcd_upper.startswith(prefix) for prefix in target_prefixes)
                    
                    if is_matched and not is_excluded:
                        matched_benefits.append({
                            "특약명": rider_name,
                            "보험사": policy["company"],
                            "상태": "지급 확정 (청구 가능)",
                            "예상금액": amount,
                            "근거": f"KCD 질병코드 '{kcd_upper}'가 골절 보장 분류에 정확히 부합합니다."
                        })
                        total_estimated_payout += amount
                    elif is_excluded:
                        matched_benefits.append({
                            "특약명": rider_name,
                            "보험사": policy["company"],
                            "상태": "지급 불가 (면책)",
                            "예상금액": 0,
                            "근거": f"KCD 코드 '{kcd_upper}'는 약관상 치아파열 등 보장 제외 대상입니다."
                        })

                # B. 깁스치료비 검증 (핵심 디테일: 통깁스 vs 반깁스/부목)
                elif "깁스" in rider_name:
                    is_splint = False
                    treatment_text = (treatment_name or "") + (treatment_code or "")
                    
                    for ex in rider.get("exclusion_keywords", []):
                        if ex.lower() in treatment_text.lower():
                            is_splint = True
                            break
                    
                    if is_splint:
                        matched_benefits.append({
                            "특약명": rider_name,
                            "보험사": policy["company"],
                            "상태": "지급 불가 (면책 주의)",
                            "예상금액": 0,
                            "근거": "약관상 '석고붕대(통깁스)' 치료만 보장되며, '부목(반깁스)' 치료는 지급 대상에서 제외됩니다."
                        })
                    elif any(target in treatment_text for target in rider.get("target_edi_codes", [])) or "통깁스" in treatment_text:
                        matched_benefits.append({
                            "특약명": rider_name,
                            "보험사": policy["company"],
                            "상태": "지급 확정 (청구 가능)",
                            "예상금액": amount,
                            "근거": "석고붕대(통깁스) 처치 확인으로 지급 요건을 충족합니다."
                        })
                        total_estimated_payout += amount

                # C. 독감치료비 검증
                elif "독감" in rider_name:
                    is_flu_kcd = any(kcd_upper.startswith(prefix) for prefix in rider.get("target_kcd_prefixes", []))
                    has_antiviral = any(drug in "".join(prescribed_drugs) for drug in ["타미플루", "페라미플루", "오셀타미비르", "코미플루"])
                    if is_flu_kcd or has_antiviral:
                        matched_benefits.append({
                            "특약명": rider_name,
                            "보험사": policy["company"],
                            "상태": "지급 확정 (청구 가능)",
                            "예상금액": amount,
                            "근거": f"독감 코드({kcd_upper}) 및 항바이러스제 처방 확인으로 지급 가능합니다."
                        })
                        total_estimated_payout += amount

                # D. 질병/상해 수술비 검증
                elif "수술비" in rider_name:
                    keywords = rider.get("target_keywords", [])
                    if any(kw in (treatment_name or "") for kw in keywords):
                        matched_benefits.append({
                            "특약명": rider_name,
                            "보험사": policy["company"],
                            "상태": "지급 가능",
                            "예상금액": amount,
                            "근거": f"시술/수술 내용('{treatment_name}')이 약관상 수술 정의에 해당합니다."
                        })
                        total_estimated_payout += amount

    # 2. 실손의료비 계산 (4세대 기준)
    silson_policy = next((p for p in user.get("policies", []) if p.get("category") == "실손보험"), None)
    total_cost = cost_covered + cost_uncovered

    if silson_policy and total_cost > 0:
        cov_info = silson_policy.get("coverage", {})
        
        if not is_inpatient:
            # 통원 공제 계산
            if hospital_type == "general":
                min_deductible = cov_info.get("outpatient_deductible_general_hospital", 20000)
            elif hospital_type == "hospital":
                min_deductible = cov_info.get("outpatient_deductible_hospital", 15000)
            else:
                min_deductible = cov_info.get("outpatient_deductible_clinic", 10000)

            # 급여 본인부담금 공제: min_deductible vs 급여의 20% 중 큰 금액
            covered_deductible = max(min_deductible, int(cost_covered * 0.2))
            covered_payout = max(0, cost_covered - covered_deductible)

            # 비급여 공제: 30,000원 vs 비급여의 30% 중 큰 금액
            if cost_uncovered > 0:
                uncovered_deductible = max(cov_info.get("uncovered_deductible_min", 30000), int(cost_uncovered * 0.3))
                uncovered_payout = max(0, cost_uncovered - uncovered_deductible)
            else:
                uncovered_deductible = 0
                uncovered_payout = 0

            silson_payout = covered_payout + uncovered_payout
            
            matched_benefits.append({
                "특약명": f"{silson_policy['product_name']}(통원)",
                "보험사": silson_policy["company"],
                "상태": "지급 가능",
                "예상금액": silson_payout,
                "근거": (
                    f"총 진료비 {total_cost:,}원 중 급여 공제 {covered_deductible:,}원, "
                    f"비급여 공제 {uncovered_deductible:,}원을 차감한 예상 수령액입니다."
                )
            })
            total_estimated_payout += silson_payout
        else:
            # 입원 계산 (급여 80%, 비급여 70% 보장)
            silson_payout = int(cost_covered * 0.8) + int(cost_uncovered * 0.7)
            matched_benefits.append({
                "특약명": f"{silson_policy['product_name']}(입원)",
                "보험사": silson_policy["company"],
                "상태": "지급 가능",
                "예상금액": silson_payout,
                "근거": f"입원 의료비 총액 {total_cost:,}원에 대해 급여 80%, 비급여 70% 보장 기준 적용"
            })
            total_estimated_payout += silson_payout

    # 3. 필요 서류 안내 생성
    required_docs = [
        "진료비 계산서·영수증 (병원 원무과 발급)",
        "진료비 세부내역서 (비급여 항목 포함 필수)"
    ]
    if any(b["특약명"].startswith("골절") for b in matched_benefits if b["상태"].startswith("지급")):
        required_docs.append("X-ray 판독지가 첨부된 진단서 또는 처방전 (KCD 질병코드 필수)")
    if any(b["특약명"].startswith("독감") for b in matched_benefits if b["상태"].startswith("지급")):
        required_docs.append("처방전(환자보관용) 또는 약국 영수증 (항바이러스제명 기재)")
    if any("수술" in b["특약명"] for b in matched_benefits if b["상태"].startswith("지급")):
        required_docs.append("수술확인서 또는 진단서 (수술명 및 질병분류코드 기재)")

    return {
        "user_id": user_id,
        "matched_benefits": matched_benefits,
        "total_estimated_payout": total_estimated_payout,
        "required_documents": required_docs,
        "disclaimer": "본 분석 결과는 가입 약관 기준의 사전 예측치이며, 실제 최종 지급액은 보험사 손해사정 심사에 따라 달라질 수 있습니다."
    }


@mcp.tool()
def get_claim_documents_checklist(rider_names: List[str]) -> dict:
    """
    청구하고자 하는 특약 목록에 맞추어 병원에서 반드시 발급받아야 할 필수 서류 체크리스트를 제공합니다.
    """
    base_docs = [
        "진료비 계산서·영수증 (병원 직인 포함)",
        "진료비 세부내역서 (급여/비급여 분리)"
    ]
    specific_docs = []

    for name in rider_names:
        if "골절" in name:
            specific_docs.append("방사선(X-ray) 판독결과지 또는 골절 진단서(KCD 코드 기재)")
        elif "수술" in name:
            specific_docs.append("수술확인서 (수술명, 수술일자, 질병코드 필수)")
        elif "깁스" in name:
            specific_docs.append("의무기록 사본 또는 진단서 (통깁스/석고붕대 시술 사실 명기)")
        elif "입원" in name:
            specific_docs.append("입퇴원확인서 (입원 기간 명기)")

    return {
        "공통필수서류": base_docs,
        "특약별추가서류": list(set(specific_docs)),
        "팁": "비싼 진단서(1~2만원) 대신 질병코드가 무료로 적혀 나오는 '환자보관용 처방전'으로 대체 가능한 경우가 많으니 원무과에 먼저 확인하세요."
    }


if __name__ == "__main__":
    mcp.run()
