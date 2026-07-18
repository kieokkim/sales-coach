# 다음 세션 시작점

## 현재 상태
- 버전: v1.7.1 — 반품 사유내역 서술 레이어 추가 (방식A: 판정구조 무변경, 설명 레이어만)
- Eval: 92.3% (84/91), 프롬프트 보강 전후 동일, 기존 3회 평균 92.7%
  (스프레드 90.1~95.6%) 안에 듦
- 커밋: Decision 18~28 (반품 통계화 → 완전성게이트 → 반품 effect-size 금액화 →
  anchor_set 재검토 → report_date 조용한 실패 수정 → 반품 사유내역 서술 레이어)

## 이번 세션 요약 (Decision 28 — 반품 사유내역 서술 레이어)

- **발견:** 오더사유명 컬럼이 샘플 데이터(sample_offline/online*.xlsx)에
  아예 없었음 — 실제 SAP 값("반품-교환"/"반품-변심"/"반품-불량"/"빠른 반품",
  마지막만 하이픈 없는 예외)을 로컬에서 검증할 방법이 없었음. 별개로,
  완전성 게이트는 category 누락만 방어하고 카테고리 안의 서술 디테일
  (어떤 반품 사유를 얼마나 강조하는지)은 방어 범위 밖이라는 구조적 한계도
  드러남.
- **원인:** 2026년 오더사유명 실측 분포(반품 내부 비중 근사 빠른반품60%/
  변심28%/교환10%/불량2%) 확보 배경 — 실측치 기반으로 샘플데이터에 합성
  컬럼을 만들어야 로컬 검증이 가능했음.
- **조치:** 방식A 구현 — `scripts/add_return_reason.py`로 샘플데이터에
  오더사유명 합성 컬럼 추가(seed 42, 폴백 케이스 포함) → `config.py`
  `RETURN_REASON_MAP` 하드코딩 매핑 → `pattern_nodes.py`
  `_return_reason_breakdown()`(반품이상 발동일에 한해 rule 집계, 판정
  로직과 완전 분리) → `context_builder.py`/`insight_node.py` 컨텍스트·
  완전성 게이트 문장 반영 → 프롬프트 지침 2단계 보강("사유 있으면 반드시
  언급, 큰 금액부터").
- **결과:** 반품이상 트리거 20일 판정 완전 동일(Step2-0 전후 91일 스윕
  검증) — 판정 로직 무변경 확인. eval 92.3%로 회귀 없음. 정상 경로 LLM
  실측 4건 전부 금액 인용 왜곡 0건, 서술 누락은 프롬프트 보강으로 개선됐으나
  100% 해소는 아님(완전성 게이트 방어 범위 밖이라 의도적으로 그대로 둠).

## 다음 과제
- **top_issues/risk_items 신뢰도 분기** (Decision 25에서 명시 이관). "이상/정상" 이진 판정
  대신 "확신할 수 없지만 관찰 가치는 있다"는 중간 신뢰도 표현 구조. risk_items 스키마가
  반품 카테고리를 지원하는지, eval_runner가 risk_items도 채점하는지 확인이 선행 과제.
  (Decision 28에서 확보한 오더사유명 구성비 실측치 — 방식B에서 "오늘 사유 구성비
  vs 평소 구성비" 비교 신호로 활용 가능. 단, 지금 config엔 안 넣어둠 — 실제 쓰일 때
  넣을 것.)
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
