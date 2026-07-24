# CLAUDE.md

## 이 파일의 역할
Claude Code가 세션 시작 시 자동으로 읽는 얇은 상태파일. 판단 근거 전문은
DECISION_LOG.md에 있지만 그건 Claude 웹/포트폴리오용 아카이브라 여기서
통째로 읽지 않는다. 필요한 부분만 아래 규칙대로 부분 참조.
- 정확한 커밋 해시는 여기 적지 않는다. 필요하면 git log -1 --oneline으로
  직접 확인. 해시를 문서에 박으면 다음 커밋마다 stale해짐(2026-07 실제
  경험: 177b03e로 적었다가 한 세션 만에 2커밋 밀림).

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
- HEAD: Decision 33 구현(channel 필드 도입 + 업로드 UI 유연화) 완료,
  다수 unpushed.
- 미커밋 WIP: db.py / pages/1_upload.py 중 db.py는 세션 무관 별개 변경
  그대로 방치 중(monthly_target 테이블 제거 diff). pages/1_upload.py는
  이번 세션에 전면 재작성돼 별개 WIP와 합쳐짐 — 다음 세션에서 db.py의
  monthly_target 제거 diff만 분리해 커밋할지 검토 필요.
- 2026-07 세션: Decision 32 버그 3건 전부 수정 완료 → Decision 33(매장
  채널구분 하드코딩 발견, 설계결정) → 이번 세션에 실제 구현까지 완료.
  channel 필드가 daily_kpi 스키마엔 이미 있었지만 db_nodes.py/seed_db.py
  둘 다 빈 문자열로 하드코딩 삽입해온 사실을 발견, 기존 548행 백필
  (scripts/backfill_channel.py, 오프라인 273/온라인 275 — 기존 분류와
  정확히 일치 확인). report_nodes.py/pattern_nodes.py/insight_node.py
  3곳 교체 도중 **4번째 하드코딩(pages/3_report.py의 OFFLINE_PLATFORMS,
  실제 리포트 화면의 바차트 색상·채널 배지)**을 추가로 발견해 사용자
  확인 후 범위 포함, 함께 수정. 업로드 UI는 다중파일+컬럼시그니처
  자동판별(S/O sum·S/O수량=오프라인, 총금액·청구수량=온라인)로 재설계,
  graph.py/load_nodes.py는 안 건드림(오프라인/온라인 파일들을 채널별로
  병합해 임시 xlsx 하나씩으로 만들어 기존 offline_path/online_path
  인터페이스 그대로 유지). tests/test_channel_field.py 신규 6케이스
  (신규매장 채널태깅/월누적게이트 동적인식/엑셀출력/30일추세SQL 등)
  전부 pytest 통과, 기존 34개 포함 전체 회귀 없음. 91일 eval 94.5%
  (기존 스프레드 90.1~95.6% 이내) — anchor override 5개 날짜 개별
  재실행 전부 PASS, 91일 배치에서 0426 1건 FAIL했던 건 단독 재실행 시
  PASS로 확인돼 LLM run-to-run 비결정성 노이즈로 판정(코드 회귀 아님).
- **운영 모드 전환(2026-07-24): 취업 우선 라운드.** 판단 로직 심화보다
  포트폴리오/실사용 증거 확보가 우선. 아래 최상단 다음과제 참조.

## 다음 과제 (2026-07-24, 취업 우선 전환 — 최우선순위)
1. **백필 스크립트 결과 확인** — scripts/backfill_channel.py 실행결과
   (오프라인 273/온라인 275) 최종 사실확인 및 문서화.
2. **헬리녹스 14일치 데이터 요청** — 외부 실사용 검증의 다음 관문.
3. (2순위) **목업 기반 프론트 실구현** — 지금까지 판단 로직 위주였던
   것을 시각적으로 보여줄 수 있는 화면으로 전환.

**이번 라운드 보류(코드 변경 없음, 착수하지 않음):**
- anchor_set 확장 라벨링(2라운드: 0504/0510/0611)
- 만성신호/시간축 트랙
- 레포정리 Task1~4
- 승인게이트 action_draft 실행레이어

## 다음 과제 (2026-07, Decision 33 — channel 필드 도입 및 업로드 UI 유연화, 전부 완료)
1. ~~channel 필드를 DB 스키마에 추가~~ — **완료**. 스키마엔 이미 있었고
   실제 문제는 삽입 경로가 빈 문자열 하드코딩이었던 것 → db_nodes.py/
   scripts/seed_db.py 수정 + 기존 548행 백필(scripts/backfill_channel.py).
2. ~~report_nodes.py/pattern_nodes.py/insight_node.py 하드코딩 교체~~ —
   **완료**. 계획한 3곳 + 추가발견 pages/3_report.py까지 총 4곳 전부
   channel 필드(또는 그날 kpi_summary에서 뽑은 동적 platform 목록) 참조로
   교체, 매장이름 리스트·SQL IN절 완전 제거.
3. ~~pages/1_upload.py 다중파일+자동판별 재설계~~ — **완료**. 계획
   승인받은 대로 구현, graph.py/load_nodes.py 무변경.
   (참고: 매장 색상 매핑 최종확정 — 서울=핑크/부산=블루/제주=오렌지/
   여주=옐로우, HCC=서울·Store1=부산·Store2=제주·Store3=여주. 색상은
   매장이름이 아니라 판매처명에 포함된 지역 키워드로 매칭할 것 — 아직
   미구현, 다음 후보 과제로 이동.)

## 다음 과제 (기존, 우선순위 아님 - 세션 시작 시 확정)
- config.py MONTHLY_TARGETS 매장이름 키 딕셔너리 확장성 문제(Decision 33
  발견) - 신규 매장이 에러/라벨 없이 매장별 달성률에서 누락되고 전사
  목표 총액도 매장 수 증가에 자동대응 안 됨. channel 필드 작업과는
  별개 트랙, 재검토 필요.
- anchor_set 2라운드 라벨링 후보: 0504, 0510, 0611 (보류 — 취업우선 전환, 위 참조)
- severity 채점 확장 재검토: category는 6/6 rule과 일치, severity는 2/6 갈림
  (0518, 0606) - 지금 eval이 severity 미채점. 표본 더 쌓은 뒤 재검토.
- 고유거래건수(고객참조번호) 반품탐지 반영 검토 - 현재 qty 기준이라
  단일고객 다건반품과 절대건수 구분 안 됨.
- 0629 target_nodes.py daily_required 산식 폭발 근본수정 (현재 가드로 우회 중).
- 프로모션 대상(scope) 필드 부재 - 실사용 연동 시 재검토.
- 외부 라벨러 확보 - 헬리녹스 실사용 제안과 연결, 3단계 완주 남은 관문.
- 만성신호/시간축 트랙 - 방향은 승격됐으나 착수조건(3도메인 공통구조+실사용
  검증) 미충족, 지금 미착수 (보류 — 취업우선 전환, 위 참조).
- 레포정리 Task1~4 - 위생작업, 최후순위(Task0 분석 완료) (보류 — 취업우선
  전환, 위 참조).

## 참고 파일
- eval/eval_runner.py, eval/ground_truth.py, eval/anchor_set.json
- nodes/insight_node.py (_validate_category_by_rule / _enforce_completeness)
- nodes/pattern_nodes.py (_return_anomalies, _return_reason_breakdown)
- config.py (DOMAIN_PARAMS, classify_return_severity, RETURN_REASON_MAP)
- COMPANY_PROFILE.md, PERSONA.md

## 이번 세션 스코프 (매 세션 시작 시 채울 것)
- 트랙: 취업 우선 전환 — 문서/사실확인만, 코드 변경 없음.
- 만질 파일: DECISION_LOG.md(Tier2 D24 색인 성격표기 + D19/D25/D24 본문에
  외부 설명용 요약 블록 추가), CLAUDE.md(현재상태/다음과제 갱신).
- 완료: Tier2 D24 색인에 "프로덕션 인시던트 대응 사례" 성격표기 추가,
  D19 본문에 외부 설명용 요약 추가. D25/D24 본문 요약은 사용자가 준
  내용 일부가 누락/손상돼 보류 — 원문 재확인 후 이어서 진행.
- 참고: 이력서용 최종 목록은 사용자가 별도로 정리 — 이번 세션은 사실확인과
  레포 기술요소 서베이만 보고.