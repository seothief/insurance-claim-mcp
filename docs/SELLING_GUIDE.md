# AI 에이전트 마켓플레이스 (Agensi.io / Gumroad) 판매 및 배포 가이드

이 문서는 `insurance-claim-mcp`를 Agensi.io 및 Gumroad 등 외부 AI 마켓플레이스에 스킬/스타터 킷으로 배포하고 유료 판매하기 위한 가이드입니다.

---

## 1. 상품 구성 요소

* **`SKILL.md`**: Agensi.io, Claude Code, Cursor, Windsurf용 공식 에이전트 스킬 규격
* **`agensi-listing.json`**: Agensi.io 상품 등록용 메타데이터 (제목, 설명, 태그, 가격 추천)
* **`.env.example`**: 구매자 환경 변수 템플릿
* **`src/` & `tests/`**: FastMCP 단일 인터페이스 백엔드 및 71개 통과 테스트 스위트

---

## 2. 권장 가격 정책

* **Standard License**: $49 ~ $79 (개인 개발자 및 인디 해커용)
* **Team / Extended License**: $129 ~ $199 (기업 및 상용 서비스 탑재용)

---

## 3. Agensi.io 등록 절차

1. [https://www.agensi.io/sell](https://www.agensi.io/sell) 접속
2. `agensi-listing.json`의 내용을 양식에 붙여넣기
3. `SKILL.md` 업로드 및 저장소 링크 연결
4. Stripe / PayPal 정산 계좌 연결
