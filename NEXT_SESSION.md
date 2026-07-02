# 다음 세션 시작점 — v1.6 4단계 (anchor set 라벨링)

## 현재 상태
Eval 1: 51.6% (5월 31개 케이스)
Eval 2: 4.0/4.0
COMPANY_PROFILE.md: 신설 (이슈 히스토리 2개)
anchor_set.json: 2개 (확실한 케이스만)

## 다음 작업 1: anchor_set 라벨링 (10~20개)

### 목적
ground_truth 우선순위(수익성 > 목표미달)가 실제로 맞는지
사람이 직접 판단한 케이스로 검증.

### 라벨링 방법
아래 명령으로 날짜별 패턴 조회 후 직접 판단:
```bash
uv run python3 -c "
import sys; sys.path.insert(0, '.')
from nodes.preprocess_nodes import _preprocess_offline, _preprocess_online
from nodes.kpi_nodes import kpi_compute_node
from nodes.pattern_nodes import pattern_detect_node
from eval.ground_truth import determine_ground_truth
import pandas as pd, json

off = pd.read_excel('data/sample_offline_3months.xlsx')
on = pd.read_excel('data/sample_online_3months.xlsx')

TARGET_DATE = '20250515'  # 여기 날짜 바꿔서 확인

off_f = _preprocess_offline(off, TARGET_DATE)
on_f = _preprocess_online(on, TARGET_DATE)
state = {
    'offline_processed': off_f, 'online_processed': on_f,
    'report_date': TARGET_DATE, 'errors': [],
    'kpi_cumulative': {}, 'target_summary': {}, 'anomalies': [],
}
from nodes.kpi_nodes import kpi_compute_node
from nodes.pattern_nodes import pattern_detect_node
state = kpi_compute_node(state)
state = pattern_detect_node(state)

gt_rule = determine_ground_truth(state)
discount = state['patterns'].get('discount_sensitivity', {})
adt = state['patterns'].get('adjusted_daily_target', {})

print(f'날짜: {TARGET_DATE}')
print(f'rule GT: {gt_rule[\"category\"]} ({gt_rule[\"severity\"]})')
print(f'마진율: {discount.get(\"margin_pct_overall\", \"N/A\")}%')
print(f'순매출 vs 조정목표: {adt.get(\"achievement_vs_adjusted\", \"N/A\")}%')
print(f'잔여일: {adt.get(\"days_remaining\", \"N/A\")}일')
"
```

### 라벨링 대상 우선순위
1. 수익성문제 + 목표미달 동시 발생 날 (모호 케이스)
2. 잔여일 < 7일인 날
3. 프로모션 기간 중 날

### anchor_set.json 추가 형식
```json
"YYYY-MM-DD": {
  "top_issue_category": "반품이슈|목표미달|수익성문제|추세악화|정상",
  "severity": "high|medium|low|none",
  "note": "왜 이 판단인지 한 문장",
  "labeled_by": "human"
}
```

## 다음 작업 2: 맥락 조건부 우선순위

anchor_set 라벨링 완료 후:
- 잔여일별 수익성 vs 목표미달 판단 패턴 분석
- eval/ground_truth.py에 조건부 우선순위 반영
  (잔여일 < 7일이면 목표미달 우선순위 상승)

## 다음 작업 3: COMPANY_PROFILE 업데이트

실데이터 붙을 때:
- 계절성 수치 업데이트 (실제 데이터 기반)
- 마진율 기준 업데이트 (실제 원가 기반)
- 이슈 히스토리 누적

## 참고 파일
- eval/anchor_set.json — 현재 라벨링 현황
- eval/ground_truth.py — rule-based 판정 로직
- COMPANY_PROFILE.md — 도메인 지식 베이스
- PERSONA.md — 타겟 사용자 기준
- DECISION_LOG.md Decision 13 — 왜 여기서 멈췄는지
