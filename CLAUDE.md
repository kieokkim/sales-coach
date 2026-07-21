# CLAUDE.md

## 이 파일의 역할
Claude Code가 세션 시작 시 자동으로 읽는 얇은 상태파일. 판단 근거 전문은
DECISION_LOG.md에 있지만 그건 Claude 웹/포트폴리오용 아카이브라 여기서
통째로 읽지 않는다. 필요한 부분만 아래 규칙대로 부분 참조.

## 작업 규율 (거의 안 바뀜)
- Rule-based First: 판단(탐지/스코어링)은 deterministic rule. LLM은 설명/서술만.
- Simplicity/Surgical: 요청 기능만. 무관 리팩토링 금지. 기존 graph/state 유지.
- 새 patterns는 context_builder.py에만 추가.
- 노드마다 logger 필수, except pass 금지(logger.warning으로 대체).
- 구현 전 계획 제시, 불확실하면 질문. 범위 초과 금지.
- 원인추적과 코드수정 분리(조사만 하는 세션 허용). 디버깅 순서: 원인 -> 해결책 -> 예방법.
- 커밋: eval 회귀 없음 확인 후 분리 커밋(feat/fix/refactor/docs/chore).
- push는 명시적 지시 시에만. push 전 민감데이터(실매장명 등) 익명화 감사.
- .env/DB gitignore, final_notebook.ipynb 수정 금지.
- 세션당 한 트랙만 진행.

## 설계 철학 (제품 판단 로직)
- 구조는 universal(통계함수, nodes/에 위치, 회사 무관 불변), 파라미터는 도메인
  (config.DOMAIN_PARAMS가 single source of truth, COMPANY_PROFILE.md는 근거기록),
  상수는 통계표준값(코드 상수 + 근거 주석).
- 핵심원칙: 유의성 + 효과크기. 통계적으로 유의해도 절대 규모가 사소하면 무시.
- rule/LLM 역할분리: 수치계산은 전부 rule. 판단/서술은 LLM 3개 노드
  (insight_node/action_node/commentary_nodes)만.
- 타겟유저: PERSONA.md 기준, 본사 마케팅/영업관리 담당자, 매일 5~10분 안에
  "오늘 뭘 해야 하는지" 판단.
- 새 기능 판단 필터: "이것이 판단 품질과 직결되는가?" 아니면 보류.
  (feature-filter 스킬 참조, 세부 기준 거기 있음)

## eval 실행 규율
- 판정 로직(rule)을 건드린 변경만 91일 full eval 재실행.
- 서술/프롬프트/컨텍스트 텍스트만 바꾼 경우는 트리거된 날짜만 먼저 확인,
  필요 판단되면 그때 91일 전체.
- anchor_set override로 GT가 바뀐 날짜는 그 날짜의 PASS/FAIL만 개별로 봐야 함.
  override 안 된 날짜의 FAIL 변동을 섞어서 "효과"로 해석하지 말 것 -
  LLM run-to-run 비결정성 노이즈일 수 있음(2026-07 anchor_set 확장 세션에서
  실측 확인된 패턴).
- 판단개선/측정정상화/회귀 구분, FAIL 판별절차는 eval-discipline 스킬 참조.

## 세션 시작 시
- 이번 세션에서 만질 파일이 아래 "이번 세션 스코프"에 명시돼 있는지 확인.
  안 돼있으면 레포 전체를 탐색하지 말고 먼저 물어볼 것.
- 컨텍스트가 길어져 반복수정이 꼬이면 이어가려 하지 말고 새 세션 시작을 제안.

## DECISION_LOG.md 참조 규칙
- 통째로 읽지 말 것. 필요한 판단 근거가 있을 때만 grep "### Decision N"으로
  찾아 그 섹션만 view.
- 예: 반품 severity 문턱 근거가 필요하면 "Decision 25" 검색.

---

## 현재 상태 (세션마다 갱신, 최신 우선)
- 버전: v1.7 + 반품 사유내역 서술레이어(방식A) + anchor_set 9항목
- Eval 기준: 92.3~92.7% 스프레드(90.1~95.6%). anchor override 5개 날짜
  (0415/0426/0518/0606/0630) PASS 유지 확인됨.
- HEAD: anchor_set 병합 + Decision 31 커밋까지, 다수 unpushed.
- 미커밋 WIP: db.py / pages/1_upload.py - 세션 무관 별개 변경, 방치 중.

## 다음 과제 (2026-07 기준, 우선순위 아님 - 세션 시작 시 확정)
- anchor_set 2라운드 라벨링 후보: 0504, 0510, 0611
- severity 채점 확장 재검토: category는 6/6 rule과 일치, severity는 2/6 갈림
  (0518, 0606) - 지금 eval이 severity 미채점. 표본 더 쌓은 뒤 재검토.
- 고유거래건수(고객참조번호) 반품탐지 반영 검토 - 현재 qty 기준이라
  단일고객 다건반품과 절대건수 구분 안 됨.
- 0629 target_nodes.py daily_required 산식 폭발 근본수정 (현재 가드로 우회 중).
- 프로모션 대상(scope) 필드 부재 - 실사용 연동 시 재검토.
- 외부 라벨러 확보 - 헬리녹스 실사용 제안과 연결, 3단계 완주 남은 관문.
- 만성신호/시간축 트랙 - 방향은 승격됐으나 착수조건(3도메인 공통구조+실사용
  검증) 미충족, 지금 미착수.
- 레포정리 Task1~4 - 위생작업, 최후순위(Task0 분석 완료).

## 참고 파일
- eval/eval_runner.py, eval/ground_truth.py, eval/anchor_set.json
- nodes/insight_node.py (_validate_category_by_rule / _enforce_completeness)
- nodes/pattern_nodes.py (_return_anomalies, _return_reason_breakdown)
- config.py (DOMAIN_PARAMS, classify_return_severity, RETURN_REASON_MAP)
- COMPANY_PROFILE.md, PERSONA.md

## 이번 세션 스코프 (매 세션 시작 시 채울 것)
- 트랙:
- 만질 파일:
- 완료 기준: