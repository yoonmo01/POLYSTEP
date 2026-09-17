# POLYSTEP: 청년 정책·장학금 맞춤 안내 서비스

> 검색으로 끝나지 않고 **"지금 내가 실제로 신청할 수 있는가"** 까지 확인해주는 정책 안내 웹서비스

[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

한림대학교 "오픈소스SW의이해" 전공수업 팀 프로젝트

| | |
|---|---|
| **기간** | 2025.09 ~ 2025.12 (한 학기) |
| **팀 구성** | 4명 |
| **담당** | 팀장 · 역할 분담 · 정책 검증 파이프라인 · 백엔드 연계 |
| **데이터** | 청년정책 **407건** · 장학금 **38건** |

---

<p align="center">
  <img src="docs/images/fig3-home.png" width="820" alt="POLYSTEP 첫 화면">
</p>

## 📌 무엇을 해결하나

청년 정책은 정보가 없어서 못 받는 게 아니라, **정보가 흩어져 있고 자주 바뀌어서** 못 받습니다.

- 정책이 기관별(공공데이터포털·지자체·대학)로 흩어져 있습니다.
- 공고가 수시로 마감·변경되는데, 검색 결과에는 **이미 끝난 공고가 그대로 남아 있습니다.**
- 그래서 "검색은 됐는데 신청은 못 하는" 상황이 반복됩니다.

POLYSTEP은 정책을 찾아주는 데서 멈추지 않고, **공고 원문 사이트를 직접 확인해 아직 살아 있는 정책인지 검증**한 뒤 신청 방법까지 안내합니다. 검증에 실패하면 **왜 실패했는지 사유를 그대로 보여줍니다.**

---

## 🕸 정책 사이트 통합 그래프

<p align="center">
  <img src="docs/images/fig4-graph.png" width="820" alt="청년 정책·장학 사이트 통합 그래프">
</p>

첫 화면 아래에서 **흩어진 출처를 한 장으로** 보여줍니다. 가운데 POLYSTEP을 중심으로 온통청년 · 한국장학재단 · 정부24 · 고용24 · 복지로와 각 지자체 청년포털 등 **25개 사이트**가 뻗어 나갑니다.

**노드를 클릭하면 해당 사이트가 새 탭으로 열립니다** (`onNodeClick` → `window.open`). 찾는 정보가 POLYSTEP에 아직 없더라도 출처로 바로 건너갈 수 있게 한 장치입니다.

`force-graph`로 그리며, 노드를 끌 때 커서로 튀지 않고 천천히 따라오도록 저항을 넣었습니다.

---

## 🔄 핵심 흐름

<p align="center">
  <img src="docs/images/fig1-architecture.png" width="820" alt="POLYSTEP 시스템 구조">
</p>

```
① 조건 입력          ② 정책 탐색           ③ 공식 근거 검증        ④ 신청 안내
   나이 · 지역           DB에서 조건 매칭        브라우저 Agent가          신청 방법 · 준비 서류
   키워드 · 분류         맞춤 정책 추림          공고 원문 사이트 방문       원문 링크 제공
                                              존재 · 마감 여부 확인
                                                    │
                                         ┌──────────┴──────────┐
                                      SUCCESS                FAILED
                                    검증 완료 표시        실패 사유 함께 표시
                                                      (공고 없음 / 확인 필요 / 접속 실패)
```

팀 안에서 **기능을 더 넣자는 의견과 핵심 흐름부터 완성하자는 의견이 부딪혔을 때**, `"사용자가 실제로 신청할 수 있는가"` 를 공동 판단 기준으로 정하고 위 4단계 순서로 우선순위를 재정렬했습니다. 그 기준에 기여하지 않는 기능은 범위에서 뺐습니다.

---

## ✅ 공식 근거 검증

<p align="center">
  <img src="docs/images/fig2-core-features.png" width="820" alt="Fast Track · Deep Track 핵심 기술과 실제 화면">
</p>

이 서비스의 핵심 차별점입니다. LLM이 기억하는 정책 내용을 그대로 보여주는 대신, **공고 원문을 실제로 확인합니다.**

| 단계 | 처리 |
|---|---|
| `PENDING` | 검증 레코드 생성 |
| 원문 방문 | 브라우저 자동화 Agent가 공고 URL에 접속 (Playwright · browser-use) |
| 대조 | 정책명·내용이 페이지에 실제로 존재하는지 확인 |
| `SUCCESS` | 공고 확인됨. 신청 안내 생성 |
| `FAILED` | **실패 사유를 저장하고 화면에 표시**: `POLICY_NOT_FOUND`(공고를 찾을 수 없음) · 확인 필요 · 접속 오류 |

검증 과정은 **실시간 스크린샷으로 스트리밍**되어, 사용자가 "무엇을 근거로 이렇게 안내하는지" 직접 볼 수 있습니다.

> 실패를 숨기지 않는 것이 설계 의도입니다. 확인되지 않은 정책을 확인된 것처럼 보여주면, 사용자는 헛걸음을 하게 됩니다.

---

## 🗂 데이터 수집

| 수집기 | 출처 | 대상 |
|---|---|---|
| `gonggong_api.py` | 공공데이터포털 | 청년정책 |
| `gangone_api.py` | 강원도 | 지역 청년정책 |
| `hallym_broswer.py` | 대학 공지 (브라우저 자동화) | 장학금 |

수집 후 정규화 → 중복 검사 → 마감 정책 필터링 → UI용 정제를 거칩니다.

```
crawler/collectors/*  →  정규화(normalize_policies)  →  중복 검사(check_duplicate_policies)
                      →  생존 정책 필터  →  UI 정제  →  DB 적재용 정규화  →  DB 적재
```

**최종 데이터**: 청년정책 **407건** (`data/policies_cleaned_final.csv`) · 장학금 **38건** (`data/scholarship.csv`)

중간 산출물(수집 원본·지역별 분할본)은 저장소에 포함하지 않았습니다. 위 수집기를 돌리면 재생성됩니다.

공고 검증 과정에서 내려받은 첨부파일은 `artifact_service`가 텍스트로 추출합니다. ZIP은 풀어서 순회하고, PDF는 `pypdf`, 이미지는 `pytesseract` OCR로 처리합니다. 라이브러리가 없으면 해당 단계를 건너뛰고 사유를 메타데이터에 남깁니다.

HWP·HWPX는 **확장자 인식과 다운로드까지만** 구현했습니다. 변환은 LibreOffice headless로 PDF를 거치는 경로가 맞다고 판단했는데 학기 범위에서 우선순위가 밀려, 지금은 해당 파일에 `HWP/HWPX convert not implemented` 경고를 붙여 남깁니다. 어떤 첨부가 처리되지 않았는지 추적할 수 있게 하기 위함입니다.

---

## 🛠 기술 스택

| 계층 | 실제 사용 기술 |
|---|---|
| **Backend** | FastAPI · SQLAlchemy · Pydantic |
| **DB** | PostgreSQL (`psycopg2`) |
| **LLM** | Google Gemini (`google-generativeai`) |
| **브라우저 자동화** | `browser-use` · Playwright (공고 원문 검증 · 장학금 수집) |
| **크롤링 · 파싱** | requests (공공 API 수집) · `pypdf` (PDF 추출) · `pytesseract` (이미지 OCR) |
| **Frontend** | React · Vite (JavaScript) · `force-graph` (정책 사이트 그래프) |
| **인증** | JWT 기반 로그인 (`security.py`) |

> 벡터 DB는 사용하지 않습니다. 정책 데이터는 공고 단위로 정형화가 가능해, **RDB 조건 매칭 + 원문 실검증** 조합이 더 정확하다고 판단했습니다.

---

## 📁 프로젝트 구조

```
POLYSTEP/
├── backend/app/
│   ├── main.py                            # FastAPI 진입점
│   ├── models.py / schemas.py             # ORM 모델 · Pydantic 스키마
│   ├── security.py                        # JWT 인증
│   ├── routers/
│   │   ├── auth.py                        # 회원가입 · 로그인
│   │   ├── me.py                          # 사용자 조건 · 마이페이지
│   │   ├── policies.py                    # 정책 조회 · 검증 요청
│   │   └── scholarships.py                # 장학금 조회
│   ├── services/
│   │   ├── policy_service.py              # 조건 기반 정책 매칭
│   │   ├── policy_verification_service.py # ★ 공식 근거 검증 (SUCCESS/FAILED 판정)
│   │   ├── browser_service.py             # 브라우저 Agent · 실시간 스크린샷 스트리밍
│   │   ├── parsing_service.py             # 공고문 → 구조화 필드 변환 (LLM)
│   │   ├── final_guidance_service.py      # 신청 안내 생성
│   │   ├── llm_service.py                 # LLM 호출 래퍼
│   │   └── artifact_service.py            # 내려받은 첨부파일 텍스트 추출 (PDF · 이미지 · ZIP)
│   └── scripts/                           # 정규화 · 중복 검사 · CSV 적재
│
├── crawler/
│   ├── collectors/                        # 공공데이터 · 강원도 · 대학 장학금 수집기
│   └── pipelines_batch.py                 # 배치 수집 파이프라인
│
├── frontend/my-react-app/src/
│   ├── pages/                             # Login · Signup · Home · Question · Result · Final · MyPage
│   └── components/PolicySitesGraph.jsx    # 정책 출처 관계 시각화
│
├── data/*.csv                             # DB 적재용 최종 데이터셋
├── docs/images/                           # README 이미지
└── requirements.txt
```

---

## 🚀 실행 방법

### 사전 요구사항

| 항목 | 버전 |
|---|---|
| Python | 3.11 이상 |
| Node.js | 20 이상 |
| PostgreSQL | 14 이상 |

### 1. 백엔드

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium       # 공고 원문 검증에 필요
```

`.env` 생성:

`.env`는 프로젝트 루트(`POLYSTEP/.env`)에 둡니다.

```ini
# 필수
DATABASE_URL=postgresql+psycopg2://<user>:<password>@localhost:5432/polystep
JWT_SECRET_KEY=<임의의 시크릿>

GOOGLE_API_KEY=AIza-xxxx          # Gemini (정책 안내 생성)

# 선택
BROWSER_USE_API_KEY=<browser-use 키>
DOWNLOAD_DIR=./data/downloads
FRONTEND_ORIGIN=http://localhost:5173
```

> ⚠️ 실제 키는 커밋하지 마세요.

테이블 생성 후 서버 실행:

```bash
python backend/app/create_tables.py
python backend/app/run_server.py
```

API 문서: http://127.0.0.1:8000/docs

### 2. 정책 데이터 적재

```bash
python backend/app/scripts/import_policies_from_csv.py      # 청년정책 407건
python backend/app/scripts/import_scholarships_from_csv.py  # 장학금 38건
```

### 3. 프론트엔드

```bash
cd frontend/my-react-app
npm install
npm run dev
```

http://localhost:5173

---

## 📄 라이선스

[MIT License](LICENSE)
