# 다음 세션 시작점 — v1.6 5단계 (top_issues 스키마 재설계)

## 현재 상태
- Eval 1: 64.5% (5월 31개 케이스), Eval 2: 4.0/4.0
- 이번 세션(4단계)에서 측정 설계 자체의 모순 발견 — 점수보다 구조 정상화가 먼저
- 커밋: Decision 14~16 (마진 상대기준 / severity 버그 / rule 필터)

## 핵심 발견 (왜 스키마를 바꾸는가)
insight_node 프롬프트는 "편중 등 구조적 특성은 top_issue에 쓰지 마라"고
지시하는데, eval_insight.py 채점기는 "편중 단어가 있어야 PASS"라고 요구한다.
→ 자기모순. rule 필터를 완벽히 만들어도 이 모순 때문에 점수가 안 움직인다.
표현의 우연(단어 포함 여부)이 아니라 판단의 내용(카테고리)으로 채점해야 한다.

## 다음 작업 (순서대로)

1. **insight_node 출력 스키마 변경**
   - top_issue 단일 → top_issues 복수 (상한 2, 91일 분포로 확정)
   - 각 항목에 category 필드 (LLM 자유 서술 + 5개 유형 태깅)
     반품이슈 / 수익성문제 / 목표미달 / 추세악화 / 편중
   - status는 코드가 개수로 자동도출 (0→정상, 1→주의, 2→경보)
   - relation 필드 (2개일 때만: 독립 / 연결)
   - 빈 리스트 허용 (정상인 날 = 91일 중 38.5%)

2. **insight_node 프롬프트 재작성**
   - 죽은 재강조 문구 제거 (rule 필터가 대신함)
   - "5개 유형 중 태깅" 지시 추가
   - "특이사항 없으면 빈 리스트가 정답" 명시

3. **eval_insight.py 재설계**
   - 키워드 매칭 → 카테고리 집합 비교
   - ground_truth 카테고리 집합 vs insight category 집합
   - 완전일치 PASS, 부분일치 부분점수, 정상날 둘다 빈집합이면 PASS

4. **context_builder.py**: top_issues 리스트 렌더링 반영

5. **5월 Eval 재실행** — 자기모순 해소로 점수 변화 확인
   (이 변화가 "측정 정상화"임을 명시. 판단이 좋아진 게 아님)

## 이후 대기 작업
- 0629 adjusted_daily_target 폭발 버그 (조정목표 28억 이상치)
- margin_deviation 실전 검증 (딥디스카운트 합성 케이스 — 91일 실측 0건 발동)
- anchor_set 라벨링 (스키마 재설계 완료 후)

## 참고 파일
- eval/count_concurrent_issues.py — 상한 2 근거 (91일 분포)
- eval/inspect_case.py — 특정 날짜 패턴 조회
- DECISION_LOG.md Decision 14~16 — 이번 세션 판단 기록
- COMPANY_PROFILE.md — 마진 28% 베이스라인
