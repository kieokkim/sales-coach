# 다음 세션 시작점

## 현재 상태
- 버전: v1.7 완료 — 반품/추세/목표/weekday 통계화 + 완전성게이트 + 반품 effect-size 재설계
- Eval: 3회 반복 평균 92.7% (스프레드 90.1~95.6%, 누락 0/273)
- HEAD: e5ca5e1 (origin 대비 2커밋 앞섬, push 전)
- 커밋: Decision 18~26 (반품 통계화 → 완전성게이트 → 반품 effect-size 금액화 → anchor_set 재검토)

## 다음 과제
- **top_issues/risk_items 신뢰도 분기** (Decision 25에서 명시 이관). "이상/정상" 이진 판정
  대신 "확신할 수 없지만 관찰 가치는 있다"는 중간 신뢰도 표현 구조. risk_items 스키마가
  반품 카테고리를 지원하는지, eval_runner가 risk_items도 채점하는지 확인이 선행 과제.
- 0629 target_nodes 산식 — daily_required가 잔여 1일+대폭 미달 시 폭발하는 근본 원인
  (target_skip_last_days 가드로 우회 중, 근본 수정은 target 시스템 의미론 변경 필요, 미해결)
- 프로모션 대상 제품(scope) 필드 부재 (Decision 26). 실사용 연동 논의 시 실제 프로모션
  관리 방식 확인 후 스키마 설계 판단.
- 외부 라벨러 확보 — 현재 anchor_set 라벨러가 rule 작성자 본인 1인이라 상관관계 존재.
  3단계("판단을 증명한다") 완주의 남은 관문.

## 참고 파일
- eval/eval_runner.py — P/R/F1 리포트
- eval/ground_truth.py — determine_ground_truth_set (집합 반환)
- eval/anchor_set.json — 사람 라벨 ground truth
- nodes/insight_node.py — _validate_category_by_rule / _enforce_completeness (게이트)
- nodes/pattern_nodes.py — _return_anomalies (Wilson + qty·금액 effect-size)
- config.py — DOMAIN_PARAMS, classify_return_severity
- DECISION_LOG.md — 전체 의사결정 이력
- COMPANY_PROFILE.md — 도메인 파라미터 근거

---

## 과거 이력 (v1.6 5단계 완료 시점 기록)

- Eval 1 완전일치: 80.6% (25/31), P 0.903 / R 0.903 / F1 0.893
- Eval 2: 3.87/4.0 (action JSON 파싱 1건 실패, 구조 무관)
- 왜 사람 라벨링인가: 0525에서 rule 우선순위(목표미달 정당)와 사람 판단(반품 우선)이
  갈리는 지점 발견 — 코드로 못 푸는 판단은 사람 라벨 영역임을 데이터로 증명.
  (이후 Decision 21에서 "정답 둘" 케이스로 정식 인정, anchor_set에 반영 완료)
