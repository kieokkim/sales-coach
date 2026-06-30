# SalesCoach Decision Log

---

### Decision 9: v1.5 commentary_nodes 마진 섹션 누락 수정

**결정:** `discount_sensitivity` 패턴을 `commentary_nodes.py`의 `_build_context`에도 반영해 AI 코멘터리에 마진/할인 정보가 포함되도록 수정한다.

**발견 과정:**
1. `insight_node`에는 `[할인율별 판매 + 마진 현황]` 섹션이 추가됐으나 `commentary_nodes._build_context`에는 누락
2. AI 코멘터리 출력 확인 시 마진율·할인 관련 언급이 전혀 없음

**구현:**
- `nodes/commentary_nodes.py` — `_build_context`에 `[할인율별 판매 + 마진 현황]` 블록 추가 (return_only 섹션 뒤, actions 앞). `patterns` 변수 선언 포함
- `nodes/commentary_nodes.py` — `system_prompt`에 마진 판단 규칙 2개 추가 (마진율 30% 미만 명시, 할인율 높고 마진율 낮은 제품 즉시 검토 지시)
- `nodes/commentary_nodes.py`, `insight_node.py`, `action_node.py` — `_SYSTEM_PROMPT` 앞에 PERSONA.md 참조 주석 추가

**교훈:** 같은 `patterns` 데이터를 여러 노드 context builder가 각자 다른 방식으로 읽는 구조에서는 한 쪽에 필드를 추가할 때 다른 쪽에 누락되기 쉽다. 새 패턴 추가 시 `_build_insight_context`와 `_build_context` 두 함수를 함께 체크하는 것을 루틴으로 만들 것.

---

### Decision 8: v1.5 product_master DB화 + 원가 컬럼 추가

**결정:** `product_master.xlsx`를 DB 테이블로 승격하고, 카테고리별 마진율 기준으로 원가(`cost_price`)를 역산해 추가. 할인율/마진율 실시간 계산의 인프라로 사용.

**구현:**
- `scripts/add_cost_price.py` — 카테고리별 마진 배율 적용해 원가 계산 후 xlsx 저장 (체어 1.35배, 테이블 1.40배, 텐트 1.50배, 나머지 1.40배)
- `db.py` — product_master 테이블 신설 (product_code PK, list_price, cost_price)
- `scripts/seed_db.py` — `seed_product_master()` 추가, `seed()` 최초 실행 시 69건 적재
- `nodes/pattern_nodes.py` — `_discount_sensitivity()` 추가: daily_product + product_master 조인 → 할인율 역산 → 버킷별 집계 → 마진율 계산

**교훈:** 거래 데이터의 판매가는 이미 할인이 적용된 최종가라서, 할인율 역산에는 반드시 정가 마스터가 필요하다. product_master를 DB에 넣어두면 이후 버전(재고 시그널, 카니발리제이션 등)에서도 제품 단위 분석의 기준점으로 재사용할 수 있다.

---

### Decision 7: v1.5 할인율 역산 설계 — product_master 조인 방식 채택

**결정:** 할인율을 별도 컬럼으로 저장하지 않고, 거래가 ÷ 정가(product_master.list_price)로 매번 역산하는 방식을 채택한다.

**발견 과정:**
1. 샘플 ERP 데이터에 할인율 컬럼이 없음 확인
2. S/O sum 컬럼은 이미 할인이 적용된 최종가임을 확인 — 할인율 역산에 product_master 조인 필수

**구현:**
- `nodes/pattern_nodes.py` — `avg_sell_price = revenue / qty` → `discount_pct = (1 - avg_sell_price / list_price) * 100`
- `nodes/pattern_nodes.py` — qty = 0인 ZRE 전용 행 예외 처리 추가
- `nodes/pattern_nodes.py` — `_discount_sensitivity()`: 할인율 구간(bucket)별 집계, 마진율 계산, top_discounted 3개 추출

**교훈:** 거래 데이터에 할인율이 없어도 정가 마스터가 있으면 역산 가능하다. 단, qty가 0인 행(ZRE 전용)을 걸러내지 않으면 ZeroDivisionError가 발생한다. product_master 조인이 필요한 계산은 preprocess 단계가 아니라 pattern 단계에서 처리해야 state flow가 깔끔하다.

---

### Decision 6: v1.4 DB 오염 데이터 발견 및 재시딩

**결정:** `salescoach.db`를 삭제하고 `scripts/seed_db.py`로 91일치 데이터를 재적재한다.

**발견 과정:**
1. `SUM(total_revenue)` 조회 시 2026-06-04/05 매출이 정상 대비 100배(116억) 비정상 수치 확인
2. 같은 날짜의 6개 플랫폼 값이 완전 동일 → 중복 적재 의심
3. Streamlit 직접 업로드 테스트 시 날짜를 2026년으로 잘못 선택한 흔적으로 결론

**구현:**
- `salescoach.db` 삭제
- `scripts/seed_db.py` 재실행 — 2025-04-01 ~ 2025-06-30 (91일) 재적재

**교훈:** 개발 중 수동 테스트 데이터와 시딩 데이터가 같은 DB에 섞이면 디버깅이 오염된다. 테스트 날짜는 반드시 샘플 데이터 범위(2025-04-01~06-30) 안에서 선택해야 하며, 테스트 후 DB 상태를 정기적으로 확인하는 습관이 필요하다.

---

### Decision 5: v1.4 고객 코호트 → 구매 패턴 분석으로 피벗

**결정:** "고객 코호트 분석"에서 "거래(참조번호) 단위 구매 패턴 분석"으로 범위를 재정의한다.

**발견 과정:**
ERP 원본 데이터에 고객 식별자가 없어 신규/재구매 코호트 추적이 원천적으로 불가능함을 확인. 참조번호는 거래(주문) 단위 식별자라 동일 고객의 재방문을 구분할 방법이 없음.

**구현:**
- `nodes/pattern_nodes.py` — `_purchase_combo()` 추가: 거래별 Helinox+HCC 교차구매 비율, 카테고리 조합 TOP5
- `nodes/pattern_nodes.py` — `_basket_metrics()` 추가: 채널별 거래당 평균 아이템 수/금액
- `nodes/pattern_nodes.py` — `_time_pattern()` 추가: 오늘 요일 + 30일 요일별 평균 매출
- `nodes/pattern_nodes.py` — `_basket_association()` 추가: Support/Confidence 기반 연관 제품 쌍 TOP5
- `nodes/insight_node.py` — `_build_insight_context()`에 4개 섹션 추가, `_SYSTEM_PROMPT`에 판단 기준 3개 추가

**교훈:** 데이터가 지원하지 않는 분석을 억지로 설계하지 않고 가능한 범위로 좁히는 것이 장기적으로 신뢰도를 높인다. "고객 ID 없음"이라는 데이터 한계를 포트폴리오에서 정직하게 명시하는 것이 오히려 강점이 된다.

---

### Decision 4: v1.3 채팅 한계 명시 — NO_QUERY_POSSIBLE 가드

**결정:** `daily_product`/`daily_kpi`가 거래 단위가 아니므로 답할 수 없는 질문 유형을 LLM에게 명시하고, 그런 질문에는 SQL 대신 안내 메시지를 반환한다.

**발견 과정:**
1. "체어 사면 같이 사는 제품?" 질문에 LLM이 자기참조 서브쿼리(의미 없는 SQL)를 생성해 "조회된 데이터가 없습니다"로 잘못 답변
2. DB 스키마에 거래(영수증) 단위 식별자가 없어 연관구매 질문 자체가 불가능한 구조임을 확인
3. LLM이 "모른다"는 판단을 내리지 못하고 틀린 SQL을 만들어내는 것이 근본 원인으로 확정

**구현:**
- `nodes/qa_nodes.py` — `get_schema_context()`에 한계 규칙 6번 추가 (장바구니/연관구매/고객이력 질문에는 "NO_QUERY_POSSIBLE" 반환 지시)
- `nodes/qa_nodes.py` — `generate_sql()`에 NO_QUERY_POSSIBLE 반환 분기 추가
- `nodes/qa_nodes.py` — `answer_question()`에 NO_QUERY_POSSIBLE 감지 시 안내 메시지 반환 분기 추가

**교훈:** 스키마 기반 Text-to-SQL은 "이 데이터로 답할 수 있는 질문의 경계"를 명시하지 않으면 틀린 답을 그럴듯하게 만들어낸다. "모르면 모른다고 말하게" 만드는 가드레일도 가드레일의 일종이다.

---

### Decision 3: v1.3 SQL 생성 정확도 개선 — SUM 누락 + 테이블 선택 오류

**결정:** LLM이 SQL 생성 시 `SUM()`을 누락하거나 잘못된 테이블을 참조하는 문제를 스키마 가이드 강화와 few-shot 예시 추가로 해결한다.

**발견 과정:**
1. "전체 매출 얼마야?" → SUM 없이 단일 행만 반환, 결과값 비정상
2. "V.TARP 반품 몇 건?" → `daily_product`가 아닌 `daily_kpi`에서 조회, `zre` 컬럼명 오류

**구현:**
- `nodes/qa_nodes.py` — `get_schema_context()`에 5개 규칙 추가 (SUM 필수, 테이블 선택 기준, zre_qty 컬럼명, LIKE 부분일치, 기간 패턴)
- `nodes/qa_nodes.py` — `generate_sql()`에 few-shot 예시 3개 추가

**교훈:** Text-to-SQL에서 스키마만 주면 LLM이 집계 여부와 테이블 선택을 자주 틀린다. "이 테이블은 날짜당 여러 행이 존재하므로 SUM이 필요하다"는 맥락 설명과 few-shot 예시를 함께 줘야 정확도가 올라간다.

---

### Decision 2: v1.2 판단 레이어 신설 — 에이전트 정체성 확립

**결정:** rule-based 계산 → LLM 숫자 요약 구조에서, rule-based → insight(LLM 판단) → action(LLM 액션) → commentary(LLM 서술) 3단계 판단 레이어로 전환한다.

**구현:**
- `nodes/pattern_nodes.py` — 5개 패턴 계산 함수 신설 (channel_trends, category_movers, return_anomalies, forecast, promo_effect)
- `nodes/insight_node.py` — JSON 구조화 인사이트 노드 신설 (top_issue / risk_items / opportunity_items)
- `nodes/action_node.py` — 오늘/이번 주/이번 달 액션 3개 도출 노드 신설
- `graph.py` — 15노드로 재편, `SalesDailyState`에 patterns/insights/actions 필드 추가

**교훈:** "LLM이 숫자를 읽어주는 것"과 "LLM이 판단을 내리는 것"은 구조적으로 다른 설계를 요구한다. rule-based가 수치를 계산하고 LLM은 그 수치의 의미를 해석하는 역할 분리가 전제되어야 판단의 신뢰도가 생긴다.

---

### Decision 1: v1.2 날짜 필터링 + float64 정규화

**결정:** ERP 엑셀의 판매일자 컬럼이 `float64`로 로드될 때("20250525.0") `report_date` 필터가 실패하는 문제를 `_normalize_date_col()` 헬퍼로 수정한다.

**발견 과정:**
1. 날짜 필터 적용 후에도 매출이 0원으로 나옴
2. `preprocess` 함수 단독 실행은 정상(296행/618행) — 필터 단계 문제로 범위 좁힘
3. 판매일자 dtype 확인 → `float64`, `astype(str)` 시 "20250525.0" 형태로 변환되어 "20250525"와 불일치

**구현:**
- `nodes/preprocess_nodes.py` — `_normalize_date_col()` 헬퍼 추가: `pd.to_numeric → int → str.zfill(8)`으로 int/float/str 모두 안전하게 처리
- `nodes/preprocess_nodes.py` — 날짜 필터에 `.replace("-", "")` 추가로 하이픈 형식도 허용

**교훈:** pandas로 엑셀을 읽을 때 날짜처럼 보이는 숫자 컬럼은 `int64` 또는 `float64`로 로드된다. `astype(str)`만으로는 "20250525.0" 같은 float 표현이 나올 수 있어서, `to_numeric → int → str` 변환이 더 안전하다.
