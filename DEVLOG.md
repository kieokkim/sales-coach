# SalesCoach Dev Log

세션 단위 작업 기록. 결정 자체의 근거는 DECISION_LOG.md, 여기는
"무슨 세션이 있었고 어떻게 흘러갔는지"의 흐름 기록.

---

## 2026-07-18: risk_items 신뢰도 분기 사전조사 → 착수 보류 (Decision 29, 30)

**발견:** top_issues(확정 판정)와 risk_items(보류/저확신) 사이에
"신뢰도 축"을 넣는 확장을 검토하려고, 코드 조사만 먼저 했다(조사1~4,
수정 없음). risk_items가 `list[str]`뿐이라 category/confidence를 붙일
구조가 없고, 시급성축(월누적·채널 격리)과 신뢰도축([검토] 강등)이
접두사로만 뒤섞여 있음을 확인. 조사 도중 사용자가 진짜 원하는 건
"하루 단위 저확신 신호"가 아니라 "하루론 약해도 7·30일 지속되면
구조적 문제로 확정되는 시간축 신호"임이 드러나 논의가 확장됐다.

**원인:** ①`eval/` 전체에서 `risk_items`를 읽는 코드가 0건 —
`ground_truth`가 `patterns`만 보고 top_issues/risk_items와 독립
계산되므로 risk_items는 eval 사각지대. ②완전성 게이트가 gt(rule
임계값)에 걸리는 category는 top_issues로 무조건 재삽입해서, "rule은
맞지만 확신 애매"라는 중간 상태를 만들 자리가 게이트 구조상 없음.
③신뢰도 분기의 출발점이 "합성 샘플 91일 중 0518/0630류가 EDA로 완전
분리 안 된다"는 특정 데이터 관찰이라 데이터 의존적 발상이었고, 시간축
확장도 반품 하나만 보고 설계하면 반품 전용 구조가 되는 universal 함정
+ 합성데이터라 발동 검증 불가라는 동일한 한계에 걸림.

**조치:** 코드/스키마/프롬프트 변경 없이 조사만 진행. 두 판단을
DECISION_LOG.md에 기록 — Decision 29(시간축/만성 신호 분석: 방향은
승격, 착수는 조건부 보류), Decision 30(risk_items 신뢰도 분기: 관성
배치였음을 확인하고 보류).

**결과:** 이번 세션 코드 변경 0건. 두 결정 모두 "왜 안 하는지"를
근거와 함께 남기는 것으로 종결. 다음 착수 조건: 시간축 분석은 3단계
완주 + 실사용자 + 세 번째 도메인 확보 후 반품·매출·제품추이 공통구조로
재검토, risk_items 신뢰도 분기는 eval이 risk_items를 채점하게 되거나
완전성 게이트가 category별 분기를 갖추기 전까지 보류.

---

## 2026-07-19: anchor_set 6개 확장 — severity eval 사각지대 발견 (Decision 31)

**발견:** 반품 경계선 케이스 6개 사람 라벨링 결과, category는 6/6
rule과 일치했으나 severity는 2/6이 갈렸다(0518, 0606). override 5개
날짜로 eval 재실행해봤지만 PASS/FAIL이 전혀 안 바뀌었다.

**원인:** eval_insight.py가 category set만 비교하고 severity는 애초에
채점 대상이 아니었다. 즉 Decision 18~25에서 공들여 만든 severity
effect-size 문턱이 지금까지 사람 기준으로 검증된 적이 없었고, 검증해도
현재 채점기 구조로는 점수에 반영되지 않는 사각지대였다.

**조치:** anchor_set.json에 6개 라벨 병합, override 전후로 eval
비교 실행. 발견/판단/보류 근거를 DECISION_LOG.md Decision 31로 기록
(severity 채점 확장은 갈림 표본 2건뿐이라 지금 착수 안 함, 표본 더
쌓은 뒤 재검토).

**결과:** override 5개 날짜(0415/0426/0518/0606/0630) PASS 유지 확인.
91일 전체 델타는 함께 보지 않음 — override 안 된 날짜의 FAIL 변동은
LLM run-to-run 비결정성 노이즈일 수 있어 이번 변경의 효과로 잡지
않고 별도 표기했다.

---

## 2026-07-21: 상태파일 CLAUDE.md로 통합 — COACHING_NOTES/NEXT_SESSION 은퇴

**발견:** COACHING_NOTES.md와 NEXT_SESSION.md가 같은 역할(현재상태/다음
과제)을 자처하면서 서로 다른 시점에 stale해졌다. 실사례: 이미 보류
확정된(Decision 30) risk_items 신뢰도 분기가 NEXT_SESSION.md의 "다음
과제" 목록에 그대로 남아있었다 — 결정은 DECISION_LOG.md에 기록됐지만
NEXT_SESSION.md는 그 결정을 반영하지 않은 채 멈춰 있었다.

**원인:** 세션 상태를 담는 파일이 COACHING_NOTES.md / NEXT_SESSION.md
두 개로 분산돼 있어, 한쪽만 갱신되고 다른 쪽은 방치되는 구조였다.
갱신 책임이 어느 파일에 있는지 명확하지 않았던 것이 근본 원인.

**조치:** CLAUDE.md 하나로 통합, 2구역 구성(고정규율 / 현재상태).
기존 두 파일 git rm으로 은퇴. 스킬 3개의 stale 수치 정정 —
feature-filter(SalesCoach 미검증 판단 코어를 anchor_set 9항목/category
6/6 일치/severity 2/6 갈림으로 갱신), decision-log(하드코딩된
"Decision 13까지" 예시 번호 제거, "파일 끝에서 확인" 메커니즘만 남김),
eval-discipline(anchor_set override 날짜와 비override 날짜를 분리해서
봐야 한다는 규칙 추가).

**결과:** Claude Code 세션당 자동로드 컨텍스트가 두 파일 분량에서
CLAUDE.md 하나로 축소됨. DECISION_LOG.md는 참조전용으로 격리(필요
시에만 grep으로 부분 조회, 통째로 읽지 않음).

---

## 2026-07-22: 파이프라인 전체 엣지케이스 체계적 감사 — 버그 3건 확정 (코드 수정 없음)

**발견:** 지금까지 버그(report_date 조용한 실패/Decision 27, 완전성게이트
try/except 우회/Decision 24)는 전부 실사용 검증 중 우연히 걸린 것이었다.
파이프라인 전 구간(업로드→전처리→집계→패턴탐지→LLM 3노드→리포트→채팅
QA)을 대상으로 한 의도적 사전 감사가 없었다는 점을 인지, 12개 엣지케이스를
세션 시작 전에 리스트업하고 순서대로 조사·재현했다.

**조사 방법:** 코드 추적 + 실제 재현(합성 데이터/DB 복사본으로 실행,
salescoach.db 원본은 안 건드림). 10개는 방어됨/정상으로 확인, 3개는
버그로 확정. 코드 수정은 이번 세션에서 하지 않음 — 조사와 분류만.

**결과 — 버그 3건 (전부 미수정, 우선순위는 CLAUDE.md 다음 과제 참조):**

1. sql_guard 화이트리스트 정규식 우회 — 이번 감사 최대 발견. `ALLOWED_TABLES`
   검사가 큰따옴표/대괄호/백틱으로 감싼 테이블명을 못 잡음. 복사한 DB에서
   `SELECT * FROM "product_master"` 실행 성공, 비허용 테이블인
   product_master의 cost_price(원가) 실제 조회됨. 세미콜론 스태킹은
   sqlite3 `execute()`의 "한 문장만 허용" 규칙으로 별도 방어되고 있음을
   함께 확인.
2. 완전성게이트가 API키 부재 시 우회됨 — nodes/insight_node.py:325-327
   조기 return이 try/except/완전성게이트(383번 줄)를 전부 건너뜀. Decision
   24가 고친 "호출 도중 예외" 경로와는 다른 지점이라 그때 안 잡혔음.
   합성 GT(severity=high)로 실측 재현 — top_issues가 아예 채워지지 않음.
3. 채팅 QA 빈 데이터 가드 무력화 (채팅 기능 한정, 최후순위) — `generate_answer`의
   `if not rows` 가드가 SUM()/COUNT() 집계의 `[{"col": None}]`(행 1개,
   빈 리스트 아님)를 못 잡아 LLM 호출로 새버림.

전체 판정 근거·재현 상세는 DECISION_LOG.md Decision 32 참조.

---

## 2026-07-23: 매장 채널구분 하드코딩 발견 — 업로드 UI 유연화 설계결정 (코드 수정 없음)

**발견:** 매장 매핑 확인 중 HCC=서울/Store1=부산/Store2=제주에 이어
Store3(여주)가 곧 추가되고 매장이 앞으로도 계속 늘 수 있다는 전제가
처음 명시적으로 확인됐다. 이를 계기로 코드가 매장 개수를 동적으로
다루는지 전수조사. kpi_nodes.py의 `by_platform` 집계는 groupby 기반이라
완전히 동적이지만, 오프라인/온라인 채널구분은 report_nodes.py의
`OFFLINE_PLATFORMS`, pattern_nodes.py의 SQL IN절, insight_node.py의
`_CHANNEL_NAMES` 세 곳에 매장이름이 독립적으로 하드코딩돼 있어 신규
매장이 조용히 온라인으로 오분류될 위험 확인. config.py의
`MONTHLY_TARGETS`도 매장이름 키 딕셔너리라 신규 매장이 목표 항목에서
누락되는 별개 위험도 함께 확인.

**원인:** 채널 정보는 사실 업로드 단계(오프라인/온라인 슬롯 중 어디에
파일을 넣었는지)에서 이미 확정되는데, 그 값이 DB에 저장되지 않고
버려져서 이후 코드들이 매장이름으로 채널을 각자 재추론하게 된 것이
하드코딩 3곳이 흩어진 근본원인.

**조치:** 코드 변경 없이 조사·설계결정만 진행. 근본해결 3단계(channel
필드 DB 저장 → 3곳 하드코딩을 channel 필드 참조로 교체 → 업로드 UI를
고정 2슬롯에서 다중파일+컬럼 자동판별로 재설계)를 DECISION_LOG.md
Decision 33으로 기록. 매장 색상 매핑(서울=핑크/부산=블루/제주=오렌지/
여주=옐로우, 판매처명의 지역 키워드로 매칭)도 이번 세션에 최종 확정.

**결과:** 이번 세션 코드 변경 0건. 다음 세션 스코프를 CLAUDE.md에
설정 완료 — channel 필드 도입 및 업로드 UI 유연화, 완료기준은 가상의
4번째 매장 데이터 투입 시 채널 오분류 미재현 확인까지.

---

## 2026-07-24: 취업 우선 전환 — DECISION_LOG 외부 설명용 요약 + 이력서 재료 추출 (코드 수정 없음)

**발견:** 취업 우선으로 방향이 재확정되면서, 프로젝트 완성도를 계속
파는 것보다 이미 만든 것의 가시성이 훨씬 급한 병목이라는 게 확인됐다.

**원인:** 지금까지의 작업이 전부 능력을 올리는 쪽에만 투입되고, 서류에
보이게 만드는 작업은 안 됐다.

**조치:** DECISION_LOG.md 핵심 결정 세 건(Decision 19/24/25)에 외부
설명용 요약을 덧붙이고, D24 Tier2 색인에 "프로덕션 인시던트 대응 사례"
성격표기를 추가했다. CLAUDE.md 다음과제를 취업우선 순위로 재정렬
(백필결과 확인·헬리녹스 14일치 요청 1순위, 목업 프론트 실구현 2순위,
anchor_set 확장·만성신호 트랙·레포정리 Task1-4·승인게이트
action_draft는 이번 라운드 보류). 이력서 재료 추출을 위해 레포 전체를
훑어 테스트/커밋규율/문서체계/에러처리/통계기법/라벨링 인프라 등
기술요소를 사실확인 기반으로 정리했다.

**결과:** 코드 변경 없이 기존 자산의 가시성만 높인 세션이었다.

---

## 2026-07-31: SalesCoach 데모 배포 실행 — pyproject.toml 정리, 배포 가이드, 라이브 검증, 샘플 리포트 체험 버튼

**발견:** 배포 준비(Decision 36) 마무리 세션. push 전 감사에서 API키/
비밀번호/.env 클린 확인, 지명(부산/제주/서울/여주)·HCC·헬리녹스 노출은
검토 후 민감하지 않다고 판단해 조치 불필요로 결론. pyproject.toml 정리
중 리포에 uv.lock이 남아있는 걸 재확인 — Streamlit Cloud 의존성 탐색
우선순위가 `uv.lock > requirements.txt > pyproject.toml`라 uv.lock을
방치했다면 plotly 등 3개짜리 빈약한 lock만 잡혀 streamlit 자체가 설치
안 된 채 배포가 100% 실패했을 것. 라이브 배포 후 Playwright로 실브라우저
검증하던 중, 업로드 파일 없이 리포트 생성 자체가 막혀 있는 걸 발견.

**원인:** pyproject.toml/uv.lock은 README.md가 실제 문서화한 설치법
(`uv venv` + `uv pip install -r requirements.txt`)에서 쓰이지 않는
유물로 확인, 삭제 후 requirements.txt 단일 의존성 파일로 정리.
리포트 생성 막힘은 버그가 아니라 구조적 설계 공백이었음 — 리포트 생성은
DB 조회가 아니라 업로드된 원본 오프라인/온라인 엑셀 파일 경로
(offline_path/online_path)를 그래프 파이프라인이 직접 읽는 구조
(pages/1_upload.py → 2_loading.py의 `app.invoke`)인 반면, DEMO_MODE
자동시딩(`utils/demo.py`의 `ensure_demo_data()`)은 `scripts/seed_db.py`가
같은 샘플 파일을 읽어 daily_kpi에 직접 INSERT하는 완전히 별개 경로라
7/30일 추이 비교 데이터만 채우고 리포트 생성 경로엔 닿지 않음. 로컬
개발자는 항상 자기 파일을 들고 있어 이 공백이 안 보였지만, 업로드할
파일이 없는 공개 데모 방문자는 리포트 생성 버튼 자체가 비활성 상태에
막힘.

**조치:**
- .gitignore에 screenshots/, salescoach_mockup*.html, "CLAUDE 복사본.md"
  추가(임시 산출물). scripts/backfill_from_export.py는 내용 확인 결과
  하드코딩된 민감정보 없고 파일럿 단계에 실사용 예정이라 정상 커밋.
- pyproject.toml/uv.lock 삭제 완료 재확인, DEPLOY.md 신규 작성(Streamlit
  Cloud 배포 절차 + 시크릿 설정 + Render 파일럿 전환 메모 + 라이브 검증
  체크리스트).
- 리포트 기준일 기본값을 DEMO_MODE일 때만 2025-05-01로 고정(그 외 로직
  기존 `date.today()-1` 그대로 유지, 최소 분기만 추가).
- db.py의 monthly_target 제거 WIP는 이번 세션과 무관한 별개 트랙이라
  git stash로 분리 보관("monthly_target cleanup WIP - separate session")
  — 다음 레포정리 세션 대상으로 이월.
- 리포트 생성 구조적 공백 대응: DEMO_MODE 전용 "샘플로 체험하기" 버튼을
  pages/1_upload.py에 추가, 기존 91일 샘플 파일(sample_offline_3months.xlsx
  / sample_online_3months.xlsx — seed_db.py가 쓰는 것과 동일 파일)을
  report_date=20250501로 그대로 그래프 파이프라인에 태움. 업로드 위젯이나
  기존 실사용 플로우는 무변경 — DEMO_MODE 분기 안에서만 버튼 하나
  추가하는 최소 변경. 하루치 더미가 아니라 91일 전체 baseline 위에서
  도는 완전한 리포트라 추세/목표달성률/반품이상탐지 판단 로직 전부
  포함해 동작.
- rate limit(`utils/ratelimit.py`, `check_and_record_report_generation`)
  구조 재확인 — `st.session_state` 기반 rolling 1시간 윈도우라 방문자
  세션별 독립 카운트, 다른 방문자 요청과 섞이지 않음.

**결과:** pytest 34개 전체 무회귀(판정 로직 무변경, eval 불필요).
커밋 6건 기능별 분리(chore/docs/fix/feat) 후 push, 최종 d289e4f.
Streamlit Cloud 재배포 후 라이브 검증 전항목 통과: 자동시딩 동작,
데모배너 노출, 비밀번호 게이트 DEMO_MODE 자동우회, 채팅 페이지가
입력창 없이 기능설명으로 대체, 샘플 체험 버튼으로 2025-05-01 리포트
정상 생성(빈 리포트 아님), 시간당 5건 제한 확인. 배포 URL:
https://sales-coach-demo.streamlit.app/
