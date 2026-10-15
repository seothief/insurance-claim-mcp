# 🏥 Personal Insurance Claim Matching MCP Server

대화형 AI(Claude, ChatGPT 등)가 사용자의 약봉투·영수증 사진과 증상을 분석하여, 가입된 보험 약관에서 **받을 수 있는 보험금을 1원도 빠짐없이 찾아주는 MCP(Model Context Protocol) 서버**입니다.

---

## 🚀 빠른 시작 가이드 (Quick Start)

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 서버 실행 및 테스트
FastMCP 내장 검사기(Inspector)로 웹 UI에서 바로 도구를 테스트해 볼 수 있습니다:
```bash
fastmcp dev server.py
```
또는 직접 실행:
```bash
python server.py
```

### 3. Claude Desktop / MCP 클라이언트 설정
`claude_desktop_config.json` (Windows: `%APPDATA%\Claude\claude_desktop_config.json`)에 아래 설정을 추가합니다:

```json
{
  "mcpServers": {
    "insurance-claim-agent": {
      "command": "python",
      "args": [
        "C:\\Users\\gunn-0058\\.gemini\\antigravity\\scratch\\insurance-claim-mcp\\server.py"
      ]
    }
  }
}
```

---

## 📂 프로젝트 구조

```
insurance-claim-mcp/
├── server.py               # FastMCP 서버 메인 코드 (도구 3종 구현)
├── sample_user_data.json   # 4세대 실손 + 종합보험 특약 목업 데이터
├── system_prompt.md        # 멀티모달 LLM용 이미지 분석 및 답변 프롬프트
├── requirements.txt        # 패키지 의존성 (fastmcp, pydantic)
└── README.md               # 프로젝트 안내서
```

---

## 🛠️ 제공 도구 (MCP Tools)

1. **`get_user_policies(user_id)`**
   * 사용자의 가입 보험 증권, 세부 특약(골절, 깁스, 수술비 등), 가입 금액 조회
2. **`evaluate_claim(...)`**
   * KCD 질병코드, 처치코드(EDI), 병원비(급여/비급여)를 약관과 대조
   * 실손 공제액 및 정액 특약 수령액 자동 계산
   * '반깁스 vs 통깁스' 등 약관상 면책 함정 사전 감지
3. **`get_claim_documents_checklist(rider_names)`**
   * 해당 특약 청구 시 병원에서 떼야 할 맞춤 서류 목록 반환
