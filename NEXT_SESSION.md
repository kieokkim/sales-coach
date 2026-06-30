# 다음 세션 시작점 — v1.6 Eval 레이어 준비

## 목표
`insight_node`의 판단(`top_issue`)이 사람 라벨과 일치하는지 정량 검증하는
Eval 레이어를 구축한다. 이후 모든 기능 개선의 효과를 측정 가능하게 만드는 인프라.

---

## 핵심 설계 질문

1. **ground_truth 레이블을 어떻게 만드는가?**
   - 샘플 데이터(2025-04-01~06-30)의 날짜 중 시나리오가 명확한 날짜 선별
   - 사람이 "오늘 핵심 이슈"를 직접 라벨링 → JSON 파일로 저장
   - 예: `{"date": "20250525", "top_issue": "V.TARP 반품 급증 — 60% 반품률"}`

2. **평가 지표는 무엇인가?**
   - 정확도(exact match) vs 유사도(semantic similarity)
   - LLM-as-judge 패턴 적용 여부
   - 최소 목표: 지정 날짜 5~10개 기준 정확도 70% 이상

3. **어느 레이어를 평가하는가?**
   - `insight_node` 출력(`top_issue`) — LLM 판단
   - `pattern_detect_node` 출력 — rule-based 수치 (이건 deterministic이라 별도 검증)

---

## 참조 파일

- `PERSONA.md` — 타겟 사용자 기준 (어조/깊이 판단)
- `DECISION_LOG.md` — 기존 결정 맥락
- `nodes/pattern_nodes.py` — ground_truth 규칙과 겹치는 계산 로직 있음
- `nodes/insight_node.py` — 평가 대상 함수 (`_SYSTEM_PROMPT` + `build_patterns_context`)
- `nodes/context_builder.py` — insight_node에 전달되는 context 구조
- `data/sample_offline_3months.xlsx`, `data/sample_online_3months.xlsx` — 평가용 데이터

---

## 추천 첫 스텝

```bash
# 1. 평가 대상 날짜 목록 확인
uv run python3 -c "
import sqlite3
conn = sqlite3.connect('salescoach.db')
rows = conn.execute('SELECT DISTINCT date FROM daily_kpi ORDER BY date').fetchall()
for r in rows: print(r[0])
conn.close()
"

# 2. 특정 날짜 insight_node 출력 확인 (API 키 필요)
# 날짜 선택 → 수동 라벨 작성 → eval 스크립트 구현
```

---

## 보류 항목 (이번 세션 범위 밖)
- v1.7 재고 시그널 (rule 기반, LLM 개입 여지 적음)
- v2.0 FastAPI 분리 / Langfuse
- v2.1 카니발리제이션 탐지 (Eval 이후)
