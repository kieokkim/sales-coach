# SalesCoach

> ERP 데이터 → LangGraph 파이프라인 → 판단 레이어 → 대시보드 리포트 자동 발송

일일 매출 ERP 파일을 업로드하면 KPI 분석, 타겟 달성률 계산, 이상치 탐지, 패턴 분석, AI 인사이트/액션 도출, 코멘터리 생성까지 자동으로 처리하고 HTML 이메일 또는 Excel 리포트로 발송합니다.

---

## 왜 만들었나

전 직장에서 판매일보는 매일 수동으로 만들었습니다. ERP에서 데이터를 내려받고, 엑셀 피벗으로 가공하고, 예외를 수작업으로 걸러내고, 양식을 채워 메일로 발송하는 과정이 반복됐습니다. 가장 시간이 많이 걸린 건 가공과 에러 검수였고, 프로모션 여부처럼 ERP에 표기되지 않는 예외는 매번 수기로 처리해야 했습니다.

SalesCoach는 이 반복 작업을 파이프라인으로 자동화하고, 담당자가 아침 5분 안에 "오늘 무엇을 해야 하는가"를 즉시 결정할 수 있도록 설계했습니다.

---

## 매출이라는 숫자가 가리는 것

"매출이 늘었다"는 한 문장은 네 가지 다른 의미를 가릴 수 있습니다.

신규 고객이 늘어난 건지, 기존 고객이 더 산 건지(코호트),
할인 때문에 마진이 줄어든 건지(할인 민감도),
재고가 더 있었다면 더 팔 수 있었던 건지(재고 시그널),
다른 매장이나 채널에서 옮겨온 매출인지(카니발리제이션).

SalesCoach는 v1.x에서 이 네 렌즈를 하나씩 추가하고,
v2.x에서 외부 신호(날씨, 채널 간 이동)까지 통합해
"숫자가 가리는 것"을 자동으로 드러내는 것을 목표로 합니다.

---

## 주요 기능

- **LangGraph 파이프라인** — 15개 노드로 구성된 데이터 처리 흐름. 어떤 노드가 실패해도 파이프라인은 완주합니다 (graceful degradation)
- **타겟 달성률 추적** — 월별 전체 및 플랫폼별 타겟 대비 누계 달성률, 잔여 일수 기반 필요 일평균 자동 계산
- **카테고리/제품별 집계** — 대분류→중분류→소분류 계층 집계, 제품코드별 매출 및 반품률 추적, ZRE 전용(판매 없는 반품) 별도 집계
- **로컬 SQLite 누적 저장** — 일별 KPI를 로컬 DB에 누적. 월 누계, 연도별 추이 분석 가능. 보안 데이터가 외부로 나가지 않음
- **중복 방지 가드레일** — 동일 날짜 데이터를 두 번 업로드해도 DB 중복 없음 (`INSERT OR IGNORE`)
- **rule-based 이상치 탐지** — 매출 0, 음수 순영수증, 봉사료 비율 이상을 LLM 없이 탐지
- **패턴 탐지** — 7일 평균 대비 오늘 증감률, 반품률 이상 감지, 월말 매출 예측, 프로모션 효과 측정 (rule-based, LLM 없음)
- **AI 인사이트 판단** — 패턴 데이터를 LLM이 해석해 핵심 이슈/리스크/기회를 JSON 구조화 출력
- **액션 도출** — 오늘 즉시/이번 주/이번 달 3단계 액션을 담당자 단위로 명시
- **AI 코멘터리** — 인사이트와 액션을 컨텍스트로 GPT-4o-mini가 임원 보고용 코멘터리 생성. API 키 없어도 파이프라인 완주
- **인사이트 카드 UI** — 핵심 이슈, 월말 예측, 오늘 할 일 3개 카드를 대시보드 상단에 표시
- **시계열 차트** — 일별/주별/월별 매출 추이, 채널별/플랫폼별/중분류별/제품별 분석 (Plotly)
- **출력 옵션** — HTML 이메일 본문 / Excel 파일 첨부 / 둘 다 선택 가능

---

## 아키텍처

```
SalesDailyState (TypedDict)
         │
START → file_load → preprocess → kpi_compute → db_save → db_load_cumulative
                                                                    │
                                                           target_compare
                                                                    │
                                                           anomaly_detect
                                                                    │
                                                           pattern_detect  ← rule-based 패턴 계산
                                                                    │
                                                              insight     ← LLM 인사이트 판단
                                                                    │
                                                               action     ← LLM 액션 도출
                                                                    │
                                                            commentary    ← LLM 서술
                                                                    │
                                          ┌─────────────────────────┤
                                     html_only                     both               excel_only
                                          │                          │                     │
                                     build_html              build_html             build_excel
                                          │                          │                     │
                                     email_send              build_excel                  END
                                                                     │
                                                              email_send
```

**설계 원칙**: rule-based가 수치를 계산하고, LLM은 판단/도출/서술만 담당합니다. LLM 노드는 `insight_node`, `action_node`, `commentary_node` 3개. 계산은 LLM에 맡기지 않습니다.

---

## 기술 스택

| 구분 | 사용 기술 |
|------|-----------|
| 파이프라인 | LangGraph, LangChain |
| LLM | GPT-4o-mini (langchain-openai) |
| 데이터 처리 | pandas, openpyxl |
| 로컬 DB | SQLite |
| 리포트 | Jinja2 (HTML), openpyxl (Excel) |
| UI | Streamlit, Plotly |
| 이메일 | SMTP (Gmail) |

**로드맵 추가 예정**: ChromaDB(RAG) · FastAPI · Langfuse

---

## 파일 구조

```
sales-daily-agent/
├── graph.py                 # SalesDailyState + LangGraph 그래프 (15노드)
├── config.py                # 타겟, 플랫폼 매핑, 임계값, 프로모션
├── db.py                    # SQLite 초기화 + 공통 get_db()
├── streamlit_app.py
├── pages/
│   ├── 1_upload.py          # 파일 업로드 + 날짜 선택 + 옵션 설정
│   ├── 2_loading.py         # 파이프라인 실행 + 단계별 체크리스트
│   └── 3_report.py          # 인사이트 카드 + KPI 대시보드 + 시계열 차트
├── nodes/
│   ├── load_nodes.py
│   ├── preprocess_nodes.py  # ERP 데이터 정제 + 날짜 필터
│   ├── kpi_nodes.py         # 매출/영수증/포인트 + 카테고리/제품별 집계
│   ├── db_nodes.py          # SQLite 저장 + 월 누계 + 30일 제품 누적 조회
│   ├── target_nodes.py      # 타겟 달성률 계산
│   ├── anomaly_nodes.py     # rule-based 이상치 탐지
│   ├── pattern_nodes.py     # 7일 평균/반품률/월말예측/프로모션 효과
│   ├── insight_node.py      # LLM 인사이트 판단 (JSON 구조화)
│   ├── action_node.py       # LLM 액션 도출 (3단계)
│   ├── commentary_nodes.py  # LLM 서술형 코멘터리
│   ├── report_nodes.py      # HTML + Excel 리포트 빌드
│   └── email_nodes.py       # SMTP 발송
├── scripts/
│   └── seed_db.py           # 샘플 데이터 DB 사전 적재 (최초 1회)
├── templates/
│   └── report.html          # 이메일용 HTML 템플릿
├── utils/
│   └── styles.py            # Streamlit CSS 커스터마이징
└── data/
    ├── sample_offline_3months.xlsx  # 오프라인 샘플 91일치
    ├── sample_online_3months.xlsx   # 온라인 샘플 91일치
    └── product_master.xlsx          # 제품 마스터 (69개)
```

---

## 실행 방법

```bash
# 1. 레포 클론
git clone https://github.com/kieokkim/sales-coach.git
cd sales-coach

# 2. 가상환경 생성 및 의존성 설치
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt

# 3. 환경변수 설정
cp .env.example .env
# .env 파일에 OPENAI_API_KEY, EMAIL_SENDER, EMAIL_PASSWORD 입력

# 4. 샘플 DB 사전 적재 (최초 1회 — 7일/30일 비교 데이터 생성)
uv run python scripts/seed_db.py

# 5. 실행
uv run streamlit run streamlit_app.py
```

OPENAI_API_KEY와 이메일 설정 없이도 파이프라인은 정상 실행됩니다. LLM 코멘터리와 이메일 발송만 생략됩니다.

---

## 샘플 데이터로 테스트

`data/` 디렉토리에 샘플 데이터가 포함되어 있습니다.

- `sample_offline_3months.xlsx` — 오프라인 3개 매장(HCC서울/부산/제주) 91일치 (12,803행)
- `sample_online_3months.xlsx` — 온라인 3개 플랫폼(메이크샵/네이버/카카오) 91일치 (23,159행)
- `product_master.xlsx` — 헬리녹스 제품 마스터 69개 (대분류/중분류/소분류/제품코드/단가)

샘플 데이터 기간: 2025-04-01 ~ 2025-06-30

**포함된 시나리오:**
- 어버이날 프로모션 효과 (5/1~5/10)
- V.TARP 재입고 이벤트 (5/12~5/24) + 품질 이슈로 60% 반품 (5/25)
- 계절 가중치 (6월 여름 시즌 진입)

**테스트 추천 날짜:** 2025-05-25  
→ V.TARP 반품 급증(457건), 7일 평균 대비 +192% 매출, 다채널 이상치 동시 발생

**실행 순서:**
1. `uv run python scripts/seed_db.py` (최초 1회)
2. streamlit 실행 후 날짜 2025-05-25 선택
3. 샘플 파일 2개 업로드 후 리포트 생성

---

## 타겟 설정

`config.py`의 `MONTHLY_TARGETS`에서 월별 전체 및 플랫폼별 타겟을 설정합니다.

```python
MONTHLY_TARGETS = {
    "2025-05": {
        "_total":         5_000_000_000,  # 전체 월 타겟
        "HCC":            2_000_000_000,
        "HCC 부산점":     1_000_000_000,
        "HCC 제주점":       800_000_000,
        "메이크샵":       1_200_000_000,
    },
}
```

UI의 타겟 설정 expander에서 즉석으로 입력할 수도 있습니다.

---

## 환경변수

| 변수 | 설명 | 필수 |
|------|------|------|
| `OPENAI_API_KEY` | LLM 코멘터리/인사이트/액션 생성 | 선택 |
| `EMAIL_SENDER` | 발신 Gmail 주소 | 선택 |
| `EMAIL_PASSWORD` | Gmail 앱 비밀번호 | 선택 |
| `EMAIL_RECIPIENTS` | 수신자 (쉼표 구분) | 선택 |
| `SMTP_HOST` | 기본: smtp.gmail.com | 선택 |
| `SMTP_PORT` | 기본: 587 | 선택 |

---

## 확장 계획

### 완료

| 버전 | 내용 |
|------|------|
| v1.0 | ERP → 파이프라인 → KPI 대시보드 → 이메일/Excel 발송 |
| v1.1 | 로컬 SQLite 누적, 중복 방지 가드레일, rule-based 이상치 탐지 |
| v1.2 | 카테고리/제품 집계, 패턴 탐지, LLM 인사이트/액션 판단 레이어, 시계열 차트 |

### 🔜 로드맵 — "판단 정확도" 우선

SalesCoach의 다음 단계는 **기능을 늘리는 것보다 판단의 깊이를 늘리는 것**을
우선합니다. 새 분석 영역을 고를 때 "이게 LLM의 판단을 더 정확하게/깊게
만드는가"를 먼저 묻고, 단순히 보여줄 정보만 늘리는 항목은 뒤로 미룹니다.
(타겟 사용자와 코칭 목적은 [PERSONA.md](./PERSONA.md) 참고)

| 우선순위 | 버전 | 내용 | 판단 정확도에 기여하는 지점 |
|---------|------|------|------------------------------|
| 1 | (구조 정리) | patterns 공통화 | insight/commentary가 같은 context 빌더 공유 — 반복된 누락 버그의 구조적 원인 제거 |
| 2 | v1.6 | Eval 레이어 | insight_node의 판단(top_issue)이 사람 라벨과 일치하는지 정량 검증. 이후 모든 기능의 효과를 측정 가능하게 함 |
| 3 | v2.1 | 카니발리제이션 탐지 | "매출 증가가 신규 수요인가, 채널 간 이동인가" — rule만으로 풀 수 없는 가장 어려운 판단 영역 |
| 4 | v2.0 | RAG (과거 인사이트 검색) | "이런 패턴이 전에도 있었나" 회상 → 판단에 과거 근거를 더함 |

### ⏸ 보류

판단 품질과 직결되지 않아 후순위로 미룹니다.

| 버전 | 내용 | 보류 이유 |
|------|------|-----------|
| v1.7 | 재고 시그널 | 단순 rule 기반 소진 예측, LLM 개입 여지 적음 |
| v2.0 | FastAPI 분리 / Langfuse | 인프라 전환, 판단 품질 자체에는 영향 없음 |
| v2.1 | 날씨 연동 | 외부 신호 추가는 의미 있으나 우선순위 낮음 |

**설계 원칙**: LLM은 판단(insight)·도출(action)·서술(commentary) 3개 노드만
담당합니다. 수치 계산과 비교 기준값은 전부 rule-based로 처리하므로,
기능이 늘어나도 "AI가 틀려도 숫자는 틀리지 않는" 구조는 유지됩니다.

---

## 관련 프로젝트

- [TradeCoach](https://github.com/kieokkim/trade-coach-v3) — LangGraph 기반 트레이딩 복기 코치. ICT 패턴 탐지 + 행동 교정 에이전트
