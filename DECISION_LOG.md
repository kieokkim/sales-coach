# SalesCoach Decision Log

---

### Decision 3: 채팅 인터페이스 한계 명시 — NO_QUERY_POSSIBLE 가드레일

**결정:** daily_product/daily_kpi가 날짜별 집계 테이블이므로 거래 단위 질문에는 SQL 생성 대신 정직한 안내 메시지를 반환하도록 LLM에 명시적 경계를 설정한다.

**발견 과정:**
1. "체어를 사면 같이 사는 제품이 뭐야?" 질문에 LLM이 논리적으로 의미 없는 SQL(자기참조 서브쿼리)을 생성해 "조회된 데이터가 없습니다"로 잘못 답변
2. DB 스키마에 거래(영수증) 단위 식별자가 없어 연관구매 질문 자체가 불가능한 구조임을 확인
3. LLM이 "모른다"는 판단을 내리지 못하고 틀린 SQL을 만들어내는 것이 근본 원인으로 확정

**구현/수정:**
- `nodes/qa_nodes.py` — `get_schema_context()`에 한계 규칙 6번 추가 (장바구니/연관구매/고객이력 질문에는 "NO_QUERY_POSSIBLE" 반환 지시)
- `nodes/qa_nodes.py` — `generate_sql()`에 NO_QUERY_POSSIBLE 반환 분기 추가
- `nodes/qa_nodes.py` — `answer_question()`에 NO_QUERY_POSSIBLE 감지 시 안내 메시지 반환 분기 추가

**교훈:** 스키마 기반 Text-to-SQL은 "이 데이터로 답할 수 있는 질문의 경계"를 LLM에게 명시적으로 알려주지 않으면 틀린 답을 그럴듯하게 만들어낸다. "모르면 모른다고 말하게 만드는 가드레일"도 가드레일의 일종이다.

---

### Decision 2: DB 오염 데이터 발견 및 재시딩

**결정:** salescoach.db를 삭제하고 `scripts/seed_db.py`로 91일치 데이터를 재적재한다.

**발견 과정:**
1. `SUM(total_revenue)` 조회 시 2026-06-04/05 매출이 정상 대비 100배(116억) 비정상 수치 확인
2. 같은 날짜의 6개 플랫폼 값이 완전 동일 → 중복 적재 의심
3. Streamlit 직접 업로드 테스트 시 날짜 선택 실수(2026 vs 2025)로 발생한 오염 데이터로 확정

**구현/수정:**
- `salescoach.db` 삭제
- `scripts/seed_db.py` 재실행 — 2025-04-01 ~ 2025-06-30 (91일) 재적재

**교훈:** 개발 중 수동 테스트 데이터와 시딩 데이터가 같은 DB에 섞이면 디버깅 자체가 오염된다. 테스트용 DB와 개발용 시딩 DB를 분리하거나, 수동 업로드 테스트 후 반드시 DB를 정리하는 습관이 필요하다.

---

### Decision 1: v1.4 구매 패턴 분석 — 설계 범위 피벗

**결정:** "고객 코호트 분석"에서 "거래(참조번호) 단위 구매 패턴 분석"으로 범위를 재정의한다.

**발견 과정:**
ERP 원본 데이터에 고객 식별자가 없어 신규/재구매 코호트 추적이 원천적으로 불가능함을 확인. 억지로 설계하면 의미 없는 지표가 나옴.

**구현/수정:**
- `nodes/pattern_nodes.py` — `_purchase_combo()` 추가: 거래별 Helinox+HCC 교차구매 비율, 카테고리 조합 TOP5
- `nodes/pattern_nodes.py` — `_basket_metrics()` 추가: 채널별 거래당 평균 아이템 수/금액
- `nodes/pattern_nodes.py` — `_time_pattern()` 추가: 오늘 요일 + 30일 요일별 평균 매출
- `nodes/pattern_nodes.py` — `_basket_association()` 추가: Support/Confidence 기반 연관 제품 쌍 TOP5
- `nodes/pattern_nodes.py` — `pattern_detect_node()`에 4개 함수 호출 통합
- `nodes/insight_node.py` — `_build_insight_context()`에 4개 섹션 추가
- `nodes/insight_node.py` — `_SYSTEM_PROMPT`에 판단 기준 3개 추가 (교차구매 30%↑, 요일 패턴 이슈, 연관 신뢰도 20%↑)

**교훈:** 데이터가 지원하지 않는 분석을 억지로 설계하지 않고 가능한 범위로 정직하게 좁히는 것이 장기적으로 시스템 신뢰도를 높인다. 분석 범위 재정의는 후퇴가 아니라 설계 결정이다.
