# 다음 세션 시작점 — v1.6 5단계 (anchor_set 사람 라벨링)

## 현재 상태
- Eval 1 완전일치: 80.6% (25/31), P 0.903 / R 0.903 / F1 0.893
- Eval 2: 3.87/4.0 (action JSON 파싱 1건 실패, 구조 무관)
- 커밋: Decision 14~17 (마진 상대기준 / severity 버그 / rule 필터 / category 게이트)

## 왜 사람 라벨링인가
남은 FAIL 6건 중 핵심은 rule로 못 푸는 것들:
- 0525: adt.severity=high라 rule은 목표미달 정당하나, 사람 anchor는 반품 우선
  → rule 우선순위와 사람 판단이 갈리는 지점 (목표미달 정당하나 사람은 반품 우선)
→ 이 영역은 사람 라벨링으로만 검증 가능. 이번 세션이 그 이유를 데이터로 증명함.

## 작업
1. 모호 케이스 라벨링 (10~20개)
   - eval/inspect_case.py로 날짜별 조회
   - anchor_set.json에 {categories: [...], note, labeled_by} 형식으로 추가
   - 우선 대상: 추세악화 관련 FAIL, 2개 이슈 동시발생 날(목표미달+반품)
2. anchor_set 반영 후 5월 Eval 재실행 — rule ground_truth와 사람 라벨 일치도 확인
3. 단일 라벨러 한계는 DECISION_LOG에 명시 (숨기지 않음)

## 이후 대기
- 0629 target_nodes 산식 결정
- margin_deviation 딥디스카운트 합성 케이스 검증
- 추세악화 게이트 확장 여부

## 참고 파일
- eval/eval_runner.py — P/R/F1 리포트
- eval/ground_truth.py — determine_ground_truth_set (집합 반환)
- nodes/insight_node.py — _validate_category_by_rule (게이트)
- DECISION_LOG.md Decision 14~17
- COMPANY_PROFILE.md — 마진 28% 베이스라인

---

## 참고 — 향후 재검토 시 (지금 착수 안 함)
- 프로모션 대상 제품(scope) 필드 부재 (Decision 26). 실사용 연동 논의
  시 실제 프로모션 관리 방식 확인 후 스키마 설계 판단.
