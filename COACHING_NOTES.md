# SalesCoach — Coaching Notes

설계 결정, 버전별 기능 요약, 운영 원칙을 기록한다.
코드 변경 이유는 DECISION_LOG.md에, 여기는 "지금 어디 있는가"를 기록.

---

## 현재 버전: v1.6 4단계 완료 (top_issues 복수화 + category 게이트)

---

## 이번 세션 완료 사항 (v1.6 4단계 A/B/C)

### 스키마 재설계 완료
- top_issue(단일 str) → **top_issues(리스트 0~2개)**, 각 항목 {issue, category}
- category 6종: 반품이슈 / 수익성문제 / 목표미달 / 추세악화 / 편중 / 기타
- status는 개수로 rule 자동도출, relation(independent/linked) 2개일 때만
- 빈 리스트 = 정상인 날 정식 답 (91일 중 38.5%)
- 스코프 밖 회귀 수정: action_node.py, pages/3_report.py:447 (top_issue 직접참조)

### Eval 재설계 완료
- eval_insight.py: **키워드 매칭 폐기 → 카테고리 집합 비교** (P/R/F1)
- ground_truth.py: **determine_ground_truth_set()** 추가 (medium+ 전체 집합 반환)
  + 목표미달 low 포함 (측정 교정)

### category rule 게이트 (핵심)
- insight_node.**_validate_category_by_rule()**: LLM 태깅을 rule이 최종 검증
  - 목표미달: adt.severity none이면 제거 (달성/초과인데 태깅한 오독 차단)
  - 수익성문제: margin_deviation -3%p 초과면 제거
  - 반품이슈/추세악화: 게이트 미적용 (rule-LLM 대체로 일치)
- _enforce_track_a_isolation에 통합, 오태깅은 risk_items로 강등(정보 보존)

### 결과
- Eval 1 완전일치 64.5%→**80.6%**, P 0.758→0.903, R 0.823→0.903, F1 0.774→0.893
- Eval 2 4.0→3.87 (action JSON 파싱 1건 실패, 구조 무관)
- Decision 14~17 기록됨

### 핵심 교훈 (Claude Code가 기억할 것)
- LLM은 조건문을 계산하지 않고 확률적으로 생성함 → 명확한 수치 기준도 어김
  (달성률 164%인데 목표미달 태깅). 프롬프트 반복 실패 → **rule 게이트가 답**
- **"서술은 LLM, 분류의 정당성은 rule"** — category 자기선언 구조의 완성형
- 측정 자기모순 주의: 프롬프트 지시와 채점 기준이 어긋나면 코드 수정이 점수에
  안 잡힘. Eval 채점 로직도 판단 철학과 정합적이어야 함

### 미해결 (다음 세션 주의)
- 0629 폭발: 요일 가중치 아니라 **target_nodes.py:53 daily_required 산식**
  (잔여 1일 + 월 목표 대폭 미달 → 28억/1일). 잔여 3일 가드는 별개 엣지 방어만.
  근본 수정은 target 산식 변경이라 별도 결정 필요
- margin_deviation 91일 0건 발동 — 실전 미검증. 딥디스카운트 합성 케이스 필요
- anchor 우선순위 vs rule (0525: rule은 목표미달 정당하나 사람은 반품 우선)

---

## 버전별 완료 기능

### v1.0 ~ v1.2 (기반)
- ERP → LangGraph 파이프라인 → KPI 대시보드 → 이메일/Excel 발송
- 로컬 SQLite 누적, 중복 방지 가드레일, rule-based 이상치 탐지
- 카테고리/제품 집계, 패턴 탐지, LLM 인사이트/액션 판단 레이어, 시계열 차트
- 15노드 LangGraph 파이프라인 (graceful degradation)

### v1.3 — 대화형 분석 인터페이스
- `nodes/qa_nodes.py` — Text-to-SQL 6개 함수
  (`get_schema_context`, `sql_guard`, `generate_sql`, `execute_query`, `generate_answer`, `answer_question`)
- `pages/4_chat.py` — `st.chat_input` 기반 채팅 UI, 대화 히스토리, SQL expander
- 가드레일: SELECT 전용, 허용 테이블 화이트리스트 (`daily_kpi`/`daily_product`), LIMIT 강제
- 한계 명시: NO_QUERY_POSSIBLE 분기 (장바구니/연관구매 등 거래단위 불가 질문 처리)

### v1.4 — 구매 패턴 분석
- 고객 코호트 → 구매 패턴으로 피벗 (ERP에 고객 식별자 없음)
- `pattern_nodes.py`에 4개 함수 추가:
  - `_purchase_combo`: 동시구매, 교차브랜드, 카테고리 조합 TOP5
  - `_basket_metrics`: 채널별 거래당 아이템수/금액
  - `_time_pattern`: 요일별 분포, 30일 평균 비교
  - `_basket_association`: Support/Confidence, 연관 제품 쌍 TOP5

### v1.5 — 할인 민감도 + 마진 분석
- `scripts/add_cost_price.py` — 카테고리별 마진 배율로 원가 역산 후 xlsx 저장
  (체어 1.35배, 테이블 1.40배, 텐트 1.50배, 나머지 1.40배)
- `db.py` — `product_master` 테이블 신설 (`product_code` PK, `list_price`, `cost_price`)
- `scripts/seed_db.py` — `seed_product_master()` 추가
- `pattern_nodes.py` — `_discount_sensitivity()` 추가:
  `daily_product` + `product_master` 조인 → 할인율 역산 → 버킷별 집계 → 마진율 계산

---

## 리팩토링 (v1.5 이후)

### patterns context 빌더 공통화
- `nodes/context_builder.py` 신설 — patterns → context 문자열 변환 공통 모듈
- `insight_node._build_insight_context` → `build_patterns_context(state)` 2줄 wrapper로 교체
- `commentary_nodes._build_context` → `build_patterns_context(state)` 2줄 wrapper로 교체
- 새 patterns 키 추가 시 `context_builder.py` 하나만 수정하면 됨
- DECISION_LOG Decision 10에 기록 예정 (context_builder 공통화 리팩토링)

---

## 설계 원칙

### rule-based / LLM 역할 분리
- 수치 계산: 전부 rule-based (`pattern_nodes.py`)
- 판단/도출/서술: LLM 3개 노드만 (`insight_node`, `action_node`, `commentary_nodes`)
- "AI가 틀려도 숫자는 틀리지 않는" 구조 유지

### 타겟 사용자 (PERSONA.md 기준)
- 본사 마케팅/영업관리 담당자 (매장 3~20개, 분석 전담 인력 없음)
- 매일 아침 5~10분 안에 "오늘 뭘 해야 하는지" 판단

### context 빌더 수정 규칙
- 새 patterns 키 추가 시 `nodes/context_builder.py` 하나만 수정
- insight_node / commentary_nodes 별도 수정 불필요

---

## 판단 정확도 우선 로드맵

| 우선순위 | 내용 | 이유 |
|---------|------|------|
| 1 | v1.6 Eval 레이어 | insight_node 판단 품질 정량 검증 |
| 2 | v2.1 카니발리제이션 탐지 | rule만으로 풀 수 없는 가장 어려운 판단 영역 |
| 3 | v2.0 RAG (과거 인사이트 검색) | 판단에 과거 근거 추가 |

### 보류 항목
- v1.7 재고 시그널 — rule 기반, LLM 개입 여지 적음
- FastAPI 분리 / Langfuse — 인프라 전환, 판단 품질 직결 안 됨
- 날씨 연동 — 외부 신호, 우선순위 낮음
