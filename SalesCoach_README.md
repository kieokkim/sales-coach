# SalesCoach

> ERP 데이터 → LangGraph 파이프라인 → 대시보드 리포트 자동 발송

일일 매출 ERP 파일을 업로드하면 KPI 분석, 타겟 달성률 계산, 이상치 탐지, AI 코멘터리 생성까지 자동으로 처리하고 HTML 이메일 또는 Excel 리포트로 발송합니다.

---

## 왜 만들었나

전 직장에서 판매일보는 매일 수동으로 만들었습니다. ERP에서 데이터를 내려받고, 엑셀 피벗으로 가공하고, 예외를 수작업으로 걸러내고, 양식을 채워 메일로 발송하는 과정이 반복됐습니다. 가장 시간이 많이 걸린 건 가공과 에러 검수였고, 프로모션 여부처럼 ERP에 표기되지 않는 예외는 매번 수기로 처리해야 했습니다.

SalesCoach는 이 반복 작업을 파이프라인으로 자동화하고, 경영진이 리포트를 열자마자 "이번 달 타겟 달성 가능한가"를 즉시 판단할 수 있도록 설계했습니다.

---

## 주요 기능

- **LangGraph 파이프라인** — 12개 노드로 구성된 데이터 처리 흐름. 어떤 노드가 실패해도 파이프라인은 완주합니다 (graceful degradation)
- **타겟 달성률 추적** — 월별 전체 및 플랫폼별 타겟 대비 누계 달성률, 잔여 일수 기반 필요 일평균 자동 계산
- **로컬 SQLite 누적 저장** — 일별 KPI를 로컬 DB에 누적. 월 누계, 연도별 추이 분석 가능. 보안 데이터가 외부로 나가지 않음
- **중복 방지 가드레일** — 동일 날짜 데이터를 두 번 업로드해도 DB 중복 없음 (`INSERT OR IGNORE`)
- **rule-based 이상치 탐지** — 매출 0, 음수 순영수증, 봉사료 비율 이상을 LLM 없이 탐지
- **AI 코멘터리** — KPI 요약과 이상치를 컨텍스트로 GPT-4o-mini가 비즈니스 리포트 어조로 코멘터리 생성. API 키 없어도 파이프라인 완주
- **출력 옵션** — HTML 이메일 본문 / Excel 파일 첨부 / 둘 다 선택 가능
- **대시보드 UI** — 반원 게이지, 바 차트, 채널 뱃지 테이블을 포함한 커스텀 Streamlit 대시보드

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
                                                            commentary  ← 유일한 LLM 노드
                                                                    │
                                          ┌─────────────────────────┤
                                     html_only                     both                excel_only
                                          │                          │                      │
                                     build_html              build_html              build_excel
                                          │                          │                      │
                                     email_send              build_excel                   END
                                                                     │
                                                              email_send
```

**설계 원칙**: LLM은 `commentary_node` 단 하나. 나머지는 전부 rule-based. LLM에게 계산을 맡기지 않고 설명과 요약만 담당하게 합니다.

---

## 기술 스택

| 구분 | 사용 기술 |
|------|-----------|
| 파이프라인 | LangGraph, LangChain |
| LLM | GPT-4o-mini (langchain-openai) |
| 데이터 처리 | pandas, openpyxl |
| 로컬 DB | SQLite |
| 리포트 | Jinja2 (HTML), openpyxl (Excel) |
| UI | Streamlit |
| 이메일 | SMTP (Gmail) |

---

## 파일 구조

```
sales-daily-agent/
├── graph.py                 # SalesDailyState + LangGraph 그래프
├── config.py                # 타겟, 플랫폼 매핑, 임계값
├── db.py                    # SQLite 초기화 + 공통 get_db()
├── streamlit_app.py
├── pages/
│   ├── 1_upload.py          # 파일 업로드 + 옵션 선택
│   ├── 2_loading.py         # 파이프라인 실행 + 10단계 체크리스트
│   └── 3_report.py          # 대시보드 리포트
├── nodes/
│   ├── load_nodes.py
│   ├── preprocess_nodes.py  # ERP 데이터 정제 (오프라인/온라인)
│   ├── kpi_nodes.py         # 매출/영수증/포인트 집계
│   ├── db_nodes.py          # SQLite 저장 + 월 누계 조회
│   ├── target_nodes.py      # 타겟 달성률 계산
│   ├── anomaly_nodes.py     # rule-based 이상치 탐지
│   ├── commentary_nodes.py  # LLM 코멘터리 생성
│   ├── report_nodes.py      # HTML + Excel 리포트 빌드
│   └── email_nodes.py       # SMTP 발송
├── templates/
│   └── report.html          # 이메일용 HTML 템플릿
├── utils/
│   └── styles.py            # Streamlit CSS 커스터마이징
└── data/
    ├── sample_offline.xlsx  # 오프라인 샘플 데이터
    └── sample_online.xlsx   # 온라인 샘플 데이터
```

---

## 실행 방법

```bash
# 1. 레포 클론
git clone https://github.com/kieokkim/sales-daily-agent.git
cd sales-daily-agent

# 2. 가상환경 생성 및 의존성 설치
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt

# 3. 환경변수 설정
cp .env.example .env
# .env 파일에 OPENAI_API_KEY, EMAIL_SENDER, EMAIL_PASSWORD 입력

# 4. 실행
streamlit run streamlit_app.py
```

OPENAI_API_KEY와 이메일 설정 없이도 파이프라인은 정상 실행됩니다. LLM 코멘터리와 이메일 발송만 생략됩니다.

---

## 샘플 데이터로 테스트

`data/` 디렉토리에 포함된 샘플 데이터로 전체 파이프라인을 테스트할 수 있습니다.

- `sample_offline.xlsx` — 오프라인 지점(HCC, HCC Store 1, HCC Store 2) 7일치 거래 데이터 (236행)
- `sample_online.xlsx` — 온라인 플랫폼(네이버, 카카오페이 등) 7일치 거래 데이터 (308행)

---

## 타겟 설정

`config.py`의 `MONTHLY_TARGETS`에서 월별 전체 및 플랫폼별 타겟을 설정합니다.

```python
MONTHLY_TARGETS = {
    "2026-05": {
        "_total":     50_000_000,   # 전체 월 타겟
        "HCC":        20_000_000,
        "HCC Store 1": 12_000_000,
        "HCC Store 2":  8_000_000,
        "메이크샵":   10_000_000,
    },
}
```

UI의 타겟 설정 expander에서 즉석으로 입력할 수도 있습니다.

---

## 환경변수

| 변수 | 설명 | 필수 |
|------|------|------|
| `OPENAI_API_KEY` | LLM 코멘터리 생성 | 선택 |
| `EMAIL_SENDER` | 발신 Gmail 주소 | 선택 |
| `EMAIL_PASSWORD` | Gmail 앱 비밀번호 | 선택 |
| `EMAIL_RECIPIENTS` | 수신자 (쉼표 구분) | 선택 |
| `SMTP_HOST` | 기본: smtp.gmail.com | 선택 |
| `SMTP_PORT` | 기본: 587 | 선택 |

---

## 확장 계획

- **v1.2** — 포인트 코호트 분석 노드 추가 (신규/기존 고객 분류, 교차방문 분석)
- **v1.3** — Gmail API 자동 수집 (ERP 자동 발송 메일 파싱)
- **v2.0** — Agent Harness 구조로 전환 (다른 도메인에 동일 파이프라인 적용 가능하게)

---

## 관련 프로젝트

- [TradeCoach](https://github.com/kieokkim/trade-coach-v3) — LangGraph 기반 트레이딩 복기 코치. ICT 패턴 탐지 + 행동 교정 에이전트
