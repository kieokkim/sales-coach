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
