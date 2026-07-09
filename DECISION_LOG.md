# SalesCoach Decision Log

---

### Decision 21: 목표 정교화 — 산식폭발 캡 + 0525 복합케이스 인정

**캡+skip (구조개선):** daily_required=남은목표/잔여일이 월말 쌍곡선 발산.
캡 1.5×(월목표/총일수)로 상한 + 월말 skip(잔여 ≤3일 보류). 5월 상한
241,935,483(1.5×5B/31), 6월 275,000,000(1.5×5.5B/30). 0530 raw 2.4B→242M,
0629 해소. "달성불가 목표를 미달로 판정"하던 것 근절. 단 eval 점수엔 안 보임
(그 날들은 GT·LLM 둘 다 목표미달이라 무변동) — 판단 품질 개선이나 측정 무영향.

**인과분리 철회 (판단):** gross-vs-목표로 "반품 기인 미달" 강등 시도했으나
0525에서 미발동. 규명: 0525는 판매 소프트(gross 135M<정상 164~203M)+반품 복합.
"판매 정상, 반품만 문제"라는 전제가 안 맞음. 철회. 전 구간(4~6월) 미발동
확인 후 제거 → severity/캡 값 전부 불변(순수 되돌리기, inert 코드 삭제).

**0525 = 정답 둘 케이스 (핵심):** 사람 anchor는 반품이슈만(우선순위 판단),
rule은 반품+목표미달 둘 다(둘 다 사실). rule 버그 아님.
반품우세 강제 강등(net<0 AND 반품이상)은 판매도 진짜 부진한 날의 목표미달까지
죽이므로 오버핏 → 채택 안 함. 0525 FAIL(1/31) 정직하게 잔존.
→ "코드로 못 푸는 판단은 사람 라벨 영역"의 실증. anchor_set이 필요한 이유.

**외부화·dead config:** 목표 문턱(70/0.8/0.6) config.DOMAIN_PARAMS 이관,
ANOMALY_THRESHOLD_PCT(참조처 0) 제거. 값 동일 → 판정 결과 전 구간 불변.

**미해결(별도 과제):** _adjusted_daily_target가 state["patterns"]를 실행시점에
{}로 읽어 요일가중치·프로모 보정이 미적용되던 선재 버그 발견. 고치면 목표 수치
전반 변동 → 별도 세션 재검증 필요. 이번 작업엔 섞지 않음(재검증 격리).

---

### Decision 20: 반품 return_only 경로 효과크기 게이트 — Decision 18 대칭 완성

**결정:** 반품이슈 판정의 return_only 경로(판매 0 + 반품만)에도 return_min_count
게이트를 적용. Decision 18이 효과크기 게이트를 Wilson 비율 경로에만 넣고 절대
경로엔 빠뜨린 대칭 결손 수정. 새 파라미터 없이 기존 return_min_count(=5) 재사용.

**발견 과정 (추세 통계화 후 남은 FAIL 성격 판단에서):**
1. 5월 FAIL 2건 중 0517 = 반품 놓침. GT는 반품이슈, LLM은 정상.
2. 추적 — 0517 반품은 return_only 1건. Wilson 비율 경로(0건)가 아니라
   return_only 절대 경로에서 GT 반품이슈가 나옴.
3. return_only 경로는 `>=50건 high, else medium` — 효과크기 게이트 전무.
   1건도 medium 반품이슈로 라벨. LLM은 1건을 노이즈로 맞게 무시 → GT 과라벨.
4. 재발성 전수 — return_only 소량(<50건) 날 91일 중 3일(0501:2건, 0517:1건,
   0615:1건). 구조적 결함 확정(케이스 특수성 아님).

**구현:**
- eval/ground_truth.py — determine_ground_truth / determine_ground_truth_set
  두 경로 모두 return_only 리스트에 `zre_qty >= return_min_count` 조건 추가.
  return_only는 비율 미정의 → Wilson 없이 절대건수만(대칭의 절반).
- COMPANY_PROFILE.md — return_min_count 근거에 "적용 경로 2곳(대칭)" 명시.

**결과:**
- 0517/0501/0615 소량 return_only → GT에서 제거(∅). 0525 V.TARP 592건은 유지.
- 6월 Eval **100%** (30/30, F1 1.0) — 0615 오탐 소멸. 5월 전용 튜닝 아님 독립검증.
- 5월 Eval 90.3% (28/31). 이전 93.5 대비 하락처럼 보이나 batch FAIL 3건 중
  0501·0511은 fresh 재실행 시 GT·LLM 둘 다 ∅로 PASS = LLM 비결정성 노이즈.
  0517(구조 FAIL)은 일관 해소, 0525(목표 과다)는 예고된 보류 케이스.

**교훈:**
1. **결정론적 GT 변경의 효과는 LLM 섞인 완전일치 점수가 아니라 GT 자체로 검증한다.**
   label_card(GT 결정론)로 0517/0501/0615 ∅ 확인 = 구조 개선 확증. 완전일치
   90.3~93.5 변동은 LLM run 분산이지 회귀 아님. Decision 19의 "측정/판단 분리" 재확인.
2. Decision 18에서 게이트를 한 경로에만 넣은 것이 대칭 결손을 남겼다 — 같은
   개념(효과크기)은 모든 판정 경로에 동시 적용해야 GT 일관성이 샌다.
3. 6월(독립 기간) 100%가 5월 과적합 아님의 증거. 구조 개선은 학습기간 밖에서
   재발 오탐이 사라져야 진짜다.

---

### Decision 19: 추세악화 통계화 — 가속 z-score + 방향 게이트 (Eval 67.7→93.5%, 실체는 방향 게이트)

**결정:** 추세악화 판정의 절대 문턱(가속 -15%)을 제거하고 가속 z-score
(`(최근7일avg − 직전7일avg) / 30일 일별매출 std`)로 전환 + **방향 게이트**
(overall_direction "하락"일 때만 추세악화 후보) 추가. Decision 18(반품 통계화)의
"유의성 + 효과크기 + 방향" 템플릿을 추세에 복제한 통계화 2호.

**발견 과정:**
1. Task 0 진단 — GT가 acceleration=="가속하락"(절대 -15%)만 보고 overall_direction 무시.
2. 0518(30일 +29% 상승 중 단기 가속 -18%)을 추세악화로 오판 → 5월 추세 FAIL 주범.
3. 절대 -15% 문턱이 회사 변동성 무관·방향 무관이라 상승장 단기둔화를 못 거름.

**구현:**
- config.py — trend_z_threshold=1.5 파라미터화 (구조 universal, 값만 도메인)
- pattern_nodes.py — _trend_direction_30d에 accel_zscore 산출(statistics.pstdev),
  기존 acceleration 라벨은 표시용으로만 유지
- eval/ground_truth.py — 추세악화 = overall_direction "하락" AND accel_z ≤ -z_thr
  (determine_ground_truth / _set 두 경로 동일 조건)
- nodes/context_builder.py — 동일 조건일 때만 "⚠ 추세악화 신호" 라인 출력(display 일치)
- nodes/insight_node.py — 프롬프트 정의 교체 + category 게이트에 추세악화 rule 검증 추가
  (GT-LLM-display 삼자 조건 일치 → 0526류 LLM 오태깅 자동 제거)
- eval/label_card.py — 추세 카드에 accel_z·게이트 판정 출력(옛 -15% 텍스트 교체)

**결과:**
- 5월 Eval 완전일치 67.7% → **93.5%** (29/31), F1 0.957, 종합 90.5%
- 추세 FAIL 6 → **0건**. 남은 FAIL 2건은 반품이슈(별개)
- 0518 오판 제거(z=-0.98, 방향 상승 → 게이트 탈락), 0526 LLM 오태깅 제거(횡보)
- **v1.6 절대문턱 최고점 80.6%도 넘어섬**

**교훈 (정직 기록):**
1. **+25.8pp의 실체는 z-score가 아니라 방향 게이트다.** 0518류(상승 중 단기둔화)를
   방향으로 차단한 것이 FAIL 대부분을 없앴다. z-score(std 정규화)는 이번 케이스에서
   점수 기여는 작고 — 진짜 가치는 "다른 회사에 자동 적응하는 universal 구조" 확보다.
   측정개선(z 구조)과 판단개선(방향 게이트)을 분리해 기록해야 다음 통계화에서 착시 안 함.
2. Decision 18 대비 성공한 차이 = **방향 게이트(문맥 조건)를 유의성·효과크기와 병용**.
   통계량 단독(Wilson/ z)은 문맥(상승/하락 방향)을 모른다 — 도메인 게이트가 보완.
3. GT-pattern-display-LLM게이트 네 곳의 문턱을 한 조건으로 통일해야 순환 오태깅이 안 샌다.

---

### Decision 18: 반품 판정을 절대 문턱에서 Wilson score interval로 — 통계화 1호 (회귀 발생, 재검토 필요)

**결정:** 반품 이상 탐지의 매직넘버(배수 3배, 반품률 10%, 5배, 50건)를 제거하고
Wilson score interval(표본 크기 자동 반영)로 전환. + 선행 단위 혼합 버그 수정.
SalesCoach를 "이 데이터 전용"에서 "어떤 회사 데이터든 자동 캘리브레이션"으로
격상하려는 첫 통계화 시도. **단 5월 eval이 회귀하여 재검토 대상으로 남긴다.**

**발견 과정:**
1. anchor_set 라벨링 중 0501 코트원 블랙 오탐 발견 (반품률 20%, 12.9배)
2. 원인: 그날 판매 8개 중 반품 2건 → 소표본 비율 요동 (반품 ±1건에 배수 7.2~17.6)
3. 부수 발견 — `zre_qty`가 "행 개수(.size())"로 집계돼 판매수량합과 단위 혼합
   (분자=반품 행수, 분모=판매 수량합). Wilson 전에 이것부터 수정.
4. audit로 전체 매직넘버 전수조사 → 절대 문턱이 도메인 종속임 확인

**구현:**
- kpi_nodes.py — zre_qty 단위 혼합 버그 수정 (행개수 → 수량합)
- pattern_nodes.py — _wilson_lower_bound/_upper_bound 추가 (z=1.96, 95% 표준값),
  _return_anomalies를 "오늘 반품률 신뢰구간 하한 > 평소 신뢰구간 상한" 판정으로 재설계
- eval/ground_truth.py — 반품 severity를 통계적 격차(_return_severity)로: high= 하한이
  상한의 2배 이상, else medium. 5배/50건 매직넘버 제거 (return_only 절대경로만 유지)
- qa_nodes.py / context_builder.py / action_node.py — zre_qty "건수→수량" 문구 동기화
- DB 전체 재적재 (salescoach.db) — 저장된 zre_qty를 수량합으로 갱신 (혼합 방지)

**결과 — 회귀 (정직 기록):**
- 5월 Eval 80.6% → **64.5% (−16pt)**, FAIL 6 → 11건, Recall 0.887 → 0.769
- **목표였던 0501 코트원 오탐이 제거되지 않음** (오히려 anomaly 3건으로 증가)
- 원인: Wilson은 "과거 baseline이 대표본·저율"이면 hist_upper가 매우 타이트(5.15%)해져,
  오늘 소표본이어도 관측률이 극단(20%, 100%)이면 today_lower가 그 상한을 넘어 flag됨.
  예: HCC Camp Chair 2/2=100% → Wilson 하한 34% > 상한 12% → 걸림.
  Wilson 단독으로는 극단관측·초소표본을 충분히 penalize 못 함.
- 단위 수정이 rule GT의 반품 flag 제품·일자를 광범위 변동시켜, LLM 예측과의
  일치율이 떨어짐 (놓침 다수). 측정 정상화가 아닌 실제 회귀.

**교훈:**
1. 매직넘버를 통계로 바꾸는 방향은 옳으나, Wilson score interval 단독은
   소표본 오탐 억제에 불충분하다 — 과거 baseline이 tight-low면 오늘 소표본도 유의로 걸린다.
2. 통계적 유의성 ≠ 실무적 유의성. "today_lower 최소 분모 게이트" 또는
   effect-size 병용 등 보완이 필요하다 (Decision 19 후보).
3. GT 정의를 바꾸면 eval 점수 변화는 품질개선/측정정상화/회귀가 뒤섞인다.
   변경 전후를 같은 anchor로 재라벨링해야 순수 신호가 보인다.

---

### Decision 17: category rule 게이트 — LLM 오태깅을 rule로 강제 차단

**결정:** LLM이 태깅한 category를 rule이 최종 검증해 오태깅을 제거.
목표미달/수익성문제는 수치 기준이 명확하므로 게이트 적용.

**발견 과정:**
1. eval_insight 카테고리 집합 비교 전환 후(Decision 16) FP 10건 발견
2. 6건 심층 분석: 9건이 LLM 남발(기준 어기고 태깅), 1건만 rule-배제 억울
3. 특히 0505는 달성률 164.8%(목표 초과)인데 "목표미달" 태깅 — 명백한 오독
4. 프롬프트로 기준 준수를 지시하는 것은 이미 여러 번 실패(마진 문턱,
   월 누적 격리) → rule 게이트로 강제하는 것이 검증된 패턴

**구현:**
- nodes/insight_node.py — _validate_category_by_rule() 추가,
  _enforce_track_a_isolation에 게이트 통합
  (목표미달: adt.severity none이면 제거 / 수익성: 편차 -3%p 초과면 제거)
- eval/ground_truth.py — 목표미달 low 포함 (0515 구제, 측정 교정)
- nodes/insight_node.py — 프롬프트에 게이트 명시 (불필요 태깅 사전 감소)

**측정 완화가 아닌 이유:**
게이트는 "기준 미달인데 태깅한 것"만 제거한다. 실제 이슈를 지우지 않으므로
recall이 유지된다(하락하면 게이트 과도로 재조정). ground_truth low 포함은
실제 목표 미달인 날(72.8%)을 미달로 인정하는 교정이다.

**교훈:**
LLM에게 category를 자유롭게 태깅하게 하되, 그 정당성은 rule이 검증한다.
"창조적 서술은 LLM, 분류의 정당성은 rule"이 category 자기선언 구조의 완성형이다.
LLM이 숫자를 거꾸로 읽는 오독(달성률 164%→목표미달)은 프롬프트로 못 막는다.
rule 게이트만이 이런 오독을 결정론적으로 차단한다.

**미해결 (0629 버그 — 이번엔 못 고침):**
_adjusted_daily_target의 요일 가중치 폭발로 가정하고 잔여 3일 이하 가중치
생략 가드를 넣었으나, 실제 원인은 target_nodes.py의 daily_required =
remaining_amount / days_remaining 자체였다. 잔여 1일 + 월 목표 대폭 미달이면
28억/1일 = 28억이 되어 조정목표가 폭발한다. 가드는 별개 엣지 방어로
유지하되, 근본 수정(잔여일 적을 때 daily_required 캡 또는 조정목표 산식
변경)은 target 시스템 의미론을 건드리므로 별도 결정 필요.

---

### Decision 16: 프롬프트 재강조 2회 실패 → rule-based output 필터로 전환

**결정:** insight_node의 top_issue에서 "월 누적+채널명" 패턴을
프롬프트 지시가 아닌 rule-based 정규식 필터로 강제 격리.

**발견 과정:**
1. Decision 12(2단계)에서 트랙A/B 분리 프롬프트 설계
2. Decision 15(4단계)에서 JSON 출력 직전 재강조 문구 추가
3. 두 번 모두 5개 이상 케이스에서 여전히 "HCC 46.8%"를 top_issue로 생성
4. 프롬프트 엔지니어링의 한계로 판단 — 이 정보는 지시로 억제할 게 아니라
   구조적으로 판단 후 필터링해야 하는 대상

**구현:**
- nodes/insight_node.py — _is_monthly_cumulative_issue(),
  _enforce_track_a_isolation() 추가
- JSON 파싱 직후 rule-based로 top_issue 재검사,
  위반 시 risk_items로 이동 + 대체 top_issue 탐색
  (반품 이상 > 마진 편차 > 목표 페이스 > "정상 범위" 순으로 대체)

**검증 결과 (5월 Eval 재실행):**
- 필터 자체는 의도대로 동작 확인: 0506/0507/0508/0514는 top_issue에서
  월 누적 HCC 문구가 사라지고 risk_items로 이동, 대체 top_issue 생성됨
- 단, 정규식 엣지케이스 발견: 0509는 LLM이 "월"/"누적" 단어 없이
  "HCC 채널의 달성률이 46.8%"로만 써서 패턴 미스매치, 필터 미작동
- **Eval 1 점수: 64.5%(20/31) → 64.5%(20/31), 변화 없음.**
  FAIL 케이스 목록도 동일. 필터가 답을 바꿨음에도 정답/오답 판정 자체는
  그대로였음.

**근본 원인 — eval_insight.py와의 설계 충돌:**
eval_insight.py의 편중 카테고리 키워드는 `["편중", "집중", "비중"]`뿐이다.
그런데 insight_node의 시스템프롬프트는 "매일 반복되는 구조적 특성(브랜드
편중 등)은 top_issue에 포함하지 마세요"라고 명시적으로 지시한다.
즉 프롬프트가 의도한 "정상적인 행동"(편중을 언급 안 함)과
eval_insight.py가 요구하는 "정답 판정 조건"(편중 키워드 포함)이
서로 모순된다. 필터가 완벽히 작동해 top_issue를 "정상 범위"로
바꿔도, 이 문장에는 애초에 "편중"이라는 단어가 들어갈 수 없으므로
FAIL은 그대로 남는다. 이번 수정은 버그가 아니라 **측정 설계 자체의
한계**를 드러냈다.

**교훈:**
LLM에게 "이건 하지 마세요"를 반복해서 시켜도 안 되면,
그건 판단의 영역이 아니라 규칙의 영역일 수 있다.
프롬프트 실패 2회는 충분한 증거다 — 3번째 재강조를 시도하는 대신
rule-based 후처리로 전환하는 것이 제2원칙(Rule-based First)의
올바른 적용이다.
단, rule-based 수정이 "의도대로 동작"하는 것과 "Eval 점수를 올리는 것"은
별개다. 수정이 옳았는지는 코드가 아니라 반드시 재측정으로 확인해야
하며, 숫자가 안 움직였을 때 "필터가 실패했다"로 성급히 결론짓지 말고
필터 자체 검증(Task3)과 채점 로직(eval_insight.py) 양쪽을 모두
따로 확인해야 진짜 원인(이번 경우는 채점 로직과 프롬프트 철학의
불일치)을 찾을 수 있다.

---

### Decision 15: 편중 재등장 — insight 프롬프트 위반 + ground_truth severity 배제 버그

**결정:** 두 개의 독립적 버그를 동시에 수정.
1. insight_node가 시스템프롬프트의 "월 누적 달성률 배제" 지시를
   반복적으로 위반 → JSON 출력 직전 재강조 규칙 추가
2. ground_truth의 severity="low" candidate가 등록 조건에서 배제되어
   경미한 실제 이슈가 최하위 편중으로 오판정 → 조건 수정

**발견 과정:**
1. 마진 문턱값 교정(Decision 14) 후 5월 Eval 41.9%→58.1%,
   남은 13개 FAIL 전부 "편중" 카테고리로 재등장
2. 3개 샘플 심층 조회 — "HCC 46.8%"라는 동일 수치가
   서로 다른 날짜(5/3, 5/9)에 반복 등장하는 것을 발견,
   이는 LLM이 매번 새로 판단하지 않고 월 누적 수치를
   습관적으로 재사용하고 있다는 증거
3. 반면 5/15는 insight_node가 정확히 "오늘 순매출 72.8%"를
   짚어냈는데도 ground_truth가 severity="low"라서
   candidate 자격을 박탈, 최하위 편중으로 밀려나 FAIL 처리됨
   → 이 경우는 insight가 맞고 ground_truth가 틀림

**검증 결과 (2026-07-05, 5월 Eval 재실행):**
- Eval 1: 58.1%(18/31) → 64.5%(20/31), Eval 2 4.0/4.0 유지
- 유형B(ground_truth severity 배제) 수정은 확인됨 — 0515 FAIL→PASS 전환
- 유형A(insight 프롬프트 위반)는 재강조 문구를 추가했음에도 **여전히 실패**.
  0506/0507/0508/0509/0514 등 다수가 재강조 이후에도 그대로
  "HCC 월 달성률 46.8%"류 문장을 top_issue로 반복 생성.
  즉 이번 상승분(+6.4%p)은 전부 유형B 덕분이며, 프롬프트만으로
  월 누적 수치 억제를 강제하는 데는 실패했다.
- 다음 단계 후보: 프롬프트 재강조 대신 context에서 채널별 월 누적
  수치 자체를 top_issue 판단 대상에서 구조적으로 분리(별도 섹션 격리,
  혹은 output 후처리 필터)하는 방식 검토.

**교훈:**
같은 증상(편중 재등장)이 서로 다른 두 원인에서 나올 수 있다.
"FAIL 케이스가 전부 같은 카테고리다"라는 표면적 패턴만 보고
하나의 원인으로 단정하면 안 되고, 반드시 몇 개를 심층 조회해서
원인이 정말 동일한지 확인해야 한다.
동일 수치 반복 등장은 LLM이 실제로 매번 새로 판단하는지 아니면
습관적으로 재사용하는지를 확인하는 좋은 신호다.
또한 프롬프트 재강조가 "문서에 적었으니 지켜지겠지"로 끝나면 안 되고,
반드시 재실행으로 실제 준수 여부를 확인해야 한다 — 이번처럼
숫자가 올라도 원인이 다른 곳(유형B)일 수 있다.

---

### Decision 14: 마진 판정을 절대 문턱값에서 믹스 상대기준으로 전환

**결정:** ground_truth와 insight_node의 수익성문제 판정 기준을
"margin_pct_overall < 30%" 절대값에서
"오늘 판매 믹스의 이론 마진 대비 실제 마진 이탈폭"의 상대기준으로 전환.

**발견 과정:**
1. v1.6 3단계 Eval 51.6% 이후, 남은 FAIL을 "수익성 vs 목표미달
   정답이 둘인 케이스"로 가정하고 anchor_set 라벨링을 준비
2. 라벨링 전 선행 판별(5개 모호 케이스 심층 조회) 실행 —
   "라벨링으로 풀리는 문제인지 스키마 문제인지" 먼저 확인
3. 판별 결과: 5개 중 4개가 단일정답. "정답 둘" 가설 기각.
   → top_issues 복수 스키마 수정은 불필요 (대규모 리팩토링 회피)
4. 진짜 원인 발견: margin_pct_overall < 30% 문턱값이
   이 회사 정상 마진(실측 28.3%)과 겹쳐 91일 중 90일(98.9%) 오탐.
   product_master 이론 마진(체어 25.9%/기타 28.6%/텐트 33.3%,
   전체 평균 28.3%)과 v1.5 원가배수 설계는 서로 일치했음 —
   COMPANY_PROFILE.md의 "정상 33~35%"만 근거 없는 오류였음.

**구현:**
- nodes/pattern_nodes.py — _discount_sensitivity()에 theoretical_margin_pct,
  margin_deviation 필드 추가 (기존 필드 유지)
- eval/ground_truth.py — 수익성문제 판정을 margin_deviation 기준으로 교체
  (-5%p 이하 high, -3%p 이하 medium)
- nodes/insight_node.py — 판단 기준 프롬프트를 편차 기준으로 교체
- nodes/context_builder.py — 마진 편차 라인 노출
- COMPANY_PROFILE.md — 마진율 기준 섹션 정정

**교훈:**
오탐을 "정답이 둘인 애매한 케이스"로 착각하기 쉬웠다.
라벨링에 바로 들어가지 않고 선행 판별을 거친 덕에
스키마 리팩토링(다중 top_issue) 대신 문턱값 하나 교정으로 끝남.
절대 문턱값은 도메인마다 다른 정상 베이스라인을 반영 못 한다 —
가능하면 상대/편차 기준을 우선 검토할 것.

---

### Decision 13: v1.6 3단계 — 목표 달성 판단 5요소 정밀화 + Eval 51.6% 달성

**결정:** 목표미달 판단을 "월 누적 달성률"에서
"5가지 요소를 반영한 조정 일별 목표 대비 순매출 달성률"로 전환.
Eval 1 정확도 12.1% → 51.6%로 개선 후 anchor set 라벨링 단계로 이행.
COMPANY_PROFILE.md를 도입해 도메인 특성이 판단에 반영되는 구조 확립.

**발견 과정:**
1. v1.6 1단계(12.1%): 편중 패턴 지배 — 구조적 특성이 매일 top_issue 선택
2. v1.6 2단계(41.9%): 편중 제거 후 HCC 월 누적 달성률 패턴 발견
3. v1.6 3단계(51.6%): 5요소 적용 후 남은 FAIL 15건 →
   "수익성문제 vs 목표미달 동시 발생 시 어느 게 더 중요한가"는
   코드로 풀 수 없는 도메인 판단 문제임을 확인

**구현:**
- nodes/kpi_nodes.py — net_sales 추가 (ZOR-ZRE 순매출)
- nodes/pattern_nodes.py — _adjusted_daily_target() + 가속도 추가
- eval/ground_truth.py — 5단계 우선순위 + anchor_set 우선 참조
- eval/anchor_set.json — 사람 라벨링 케이스 (2개, 확실한 것만)
- eval/eval_insight.py — 추세악화 카테고리 추가
- nodes/insight_node.py — COMPANY_PROFILE.md 로드 + 프롬프트 반영
- nodes/context_builder.py — 조정 일별 목표 + 가속도 섹션 추가
- COMPANY_PROFILE.md — 도메인 지식 베이스 신설
  (매출 구조, 계절성, 판단 기준, 이슈 히스토리)

**결정: 51.6%에서 멈추는 이유:**
남은 FAIL 15건이 전부 ground_truth 우선순위 자체가 옳은지
모호한 케이스. 코드로 계속 조정하면 순환논리.
anchor_set 라벨링으로 ground_truth 검증 후 진행.

**다음 작업:**
1. anchor_set 라벨링 (10~20개, 수익성 vs 목표미달 모호 케이스 집중)
2. 맥락 조건부 우선순위 (잔여일 기반 동적 우선순위)
3. COMPANY_PROFILE 이슈 히스토리 누적 (매달 업데이트)

**교훈:**
에이전트가 "학습"하는 것처럼 동작하려면 세 가지 레이어가 필요하다.
1. 사람이 기입한 도메인 지식(COMPANY_PROFILE) — 즉시 반영
2. 사람이 라벨링한 anchor set — ground_truth 검증
3. 누적된 케이스의 벡터화(RAG) — v2.0 이후
지금은 1+2로 시작하고, 케이스가 쌓이면 3으로 자연스럽게 이행한다.

---

### Decision 12: v1.6 2단계 — insight_node 우선순위 교정 + 30일 추세 추가

**결정:** Eval 1 결과(12.1%)를 기반으로 insight_node가 오늘의
이상치와 장기 추세를 구분하도록 프롬프트를 재설계하고,
pattern_nodes에 30일 방향성 계산을 추가한다.

**발견 과정:**
1. Eval 1 실행 결과 80/91 케이스가 FAIL
2. 패턴 분석: 반품이슈/수익성문제 날에도 insight_node가
   일관되게 "Helinox 카테고리 편중 99%"를 top_issue로 선택
3. 원인: 샘플 데이터에서 헬리녹스 제품이 구조적으로 압도적이라
   LLM이 가장 눈에 띄는 수치를 top_issue로 고르게 됨
4. 추가 발견: 7일 평균 대비 오늘(이상치)과 30일 장기 추세(방향성)를
   구분하는 데이터 자체가 없어서 두 개념이 뒤섞임

**구현:**
- nodes/pattern_nodes.py — _trend_direction_30d() 추가
  (30일 전반/후반 평균 비교로 방향성 계산, 채널별 분리)
- nodes/context_builder.py — category_movers ⚠️ 표현 중립화,
  [30일 장기 추세] 섹션 추가
- nodes/insight_node.py — _SYSTEM_PROMPT 전면 재설계
  (트랙 A: 오늘의 신호 vs 트랙 B: 장기 흐름 명시적 분리,
   top_issue 선택 우선순위 4단계 명시)
- eval/ground_truth.py — 편중 카테고리 추가 (priority=99, 최하위)
- nodes/action_node.py, nodes/insight_node.py — JSON trailing comma
  regex 수정 (LLM 출력의 trailing comma가 json.loads 실패 유발)

**교훈:** LLM이 "가장 중요한 것"을 고르게 하려면
"가장 중요한 것의 기준"을 명시해야 한다.
"오늘 달라진 것"과 "항상 있는 것"을 구분하지 않으면
LLM은 데이터에서 가장 눈에 띄는 것을 고른다.
이상치 탐지와 추세 감지는 같은 분석이 아니며,
둘 다 필요하지만 섞이면 둘 다 잃는다.

---

### Decision 11: v1.6 Action 고도화 + Eval 1·2 구축

**결정:** action_node 출력에 scope(해결 가능 범위), expected_impact(기대효과)
필드를 추가하고, insight 정확도(Eval 1)와 action 품질(Eval 2-A, rule-based)을
자동 측정하는 eval/ 모듈을 신설한다.

**발견 과정:**
1. v1.2~v1.5에서 인사이트(코호트/할인/재고/카니발리제이션 등) 층만
   계속 깊어졌고, action_node가 만드는 액션의 구체성은 한 번도 직접
   개선한 적이 없다는 점을 인지
2. "인사이트가 깊어지면 액션도 자동으로 좋아지는가"를 검증한 적이
   없다는 점을 확인 — 데이터 → 패턴 → 인사이트 → 액션 → 실행의
   사다리에서 마지막 두 단계가 분리되어 있었음
3. 업계 agent eval 표준 조사 — component-level(insight, action 각각)과
   end-to-end(종합) 평가를 분리하는 것이 표준 패턴임을 확인.
   deterministic 체크(자동, 100% 케이스)와 LLM-as-judge(선별적)를
   나누는 것도 표준과 일치

**구현:**
- nodes/action_node.py — scope, expected_impact 필드 추가
- nodes/context_builder.py — [권장 액션] 섹션에 범위/기대효과 노출
- eval/ground_truth.py — rule 기반 정답 카테고리 자동 판정
  (반품이슈/목표미달/수익성문제/정상, 심각도 우선순위 정렬)
- eval/eval_insight.py — top_issue와 ground_truth 카테고리 키워드 매칭
- eval/eval_action.py — owner/모호표현/scope/expected_impact 4점 채점
- eval/eval_runner.py — 91일 전체 순회, Eval1(정확도%) + Eval2(평균점수)
  + Eval3(종합) 자동 리포트

**알려진 한계 (다음 작업에서 보완 필요):**
- ground_truth가 pattern_nodes.py와 같은 임계값을 사용해 순환논리
  위험이 있음 — 사람이 직접 라벨링한 anchor set(10~20개)으로
  교차검증이 필요하나 이번 범위에서는 미포함
- Eval 2-B(LLM-as-judge로 "실행 가능하고 동기부여 되는가" 채점)는
  rule-based 체크만큼 정밀하지 않아 별도 작업으로 분리

**교훈:** 인사이트를 깊게 만드는 것과 그 인사이트가 실제로 더 나은
액션으로 이어지는지는 별개의 질문이다. 후자를 검증하지 않으면
"기능은 늘었는데 진짜 좋아졌는지 모르는" 상태가 누적된다.

---

### Decision 10: patterns context 빌더 공통화 리팩토링

**결정:** `insight_node`와 `commentary_nodes`가 각자 따로 갖고 있던 patterns → context 문자열 변환 로직을 `nodes/context_builder.py`로 통합. 두 파일은 `build_patterns_context()`를 호출하는 2줄 wrapper로 교체.

**발견 과정:**
1. v1.2에서 `insight_node`에 patterns 섹션 추가 후 `commentary_nodes` 누락
2. v1.5에서 `discount_sensitivity` 추가 시 동일한 실수 반복
3. 원인 분석: 같은 정보를 두 파일에 손으로 각각 써야 하는 구조가 문제 → 한 곳만 고쳐도 양쪽에 반영되는 구조로 전환 결정

**구현:**
- `nodes/context_builder.py` 신설 — 모든 patterns 섹션 포함
  (channel_trends, category_movers, return_anomalies, forecast,
  promo_effect, purchase_combo, basket_metrics, time_pattern,
  basket_association, discount_sensitivity, insights, actions)
- `nodes/insight_node.py` — `_build_insight_context()` → 2줄 wrapper
- `nodes/commentary_nodes.py` — `_build_context()` → 2줄 wrapper
- 검증: 7/7 섹션 PASS, import 3개 OK, 15노드 확인

**교훈:** 같은 데이터를 여러 파일에서 각자 변환하는 구조는 어느 한 쪽을 빠뜨리는 실수를 구조적으로 유발한다. "새 기능 추가 시 수정할 파일이 몇 개인가"를 설계 단계에서 따져야 한다. 수정 대상이 1개가 되도록 만드는 것이 가장 안전한 구조다.

---

### Decision 9: v1.5 commentary_nodes 마진 섹션 누락 수정

**결정:** `discount_sensitivity` 패턴을 `commentary_nodes.py`의 `_build_context`에도 반영해 AI 코멘터리에 마진/할인 정보가 포함되도록 수정한다.

**발견 과정:**
1. `insight_node`에는 `[할인율별 판매 + 마진 현황]` 섹션이 추가됐으나 `commentary_nodes._build_context`에는 누락
2. AI 코멘터리 출력 확인 시 마진율·할인 관련 언급이 전혀 없음

**구현:**
- `nodes/commentary_nodes.py` — `_build_context`에 `[할인율별 판매 + 마진 현황]` 블록 추가 (return_only 섹션 뒤, actions 앞). `patterns` 변수 선언 포함
- `nodes/commentary_nodes.py` — `system_prompt`에 마진 판단 규칙 2개 추가 (마진율 30% 미만 명시, 할인율 높고 마진율 낮은 제품 즉시 검토 지시)
- `nodes/commentary_nodes.py`, `insight_node.py`, `action_node.py` — `_SYSTEM_PROMPT` 앞에 PERSONA.md 참조 주석 추가

**교훈:** 같은 `patterns` 데이터를 여러 노드 context builder가 각자 다른 방식으로 읽는 구조에서는 한 쪽에 필드를 추가할 때 다른 쪽에 누락되기 쉽다. 새 패턴 추가 시 `_build_insight_context`와 `_build_context` 두 함수를 함께 체크하는 것을 루틴으로 만들 것.

---

### Decision 8: v1.5 product_master DB화 + 원가 컬럼 추가

**결정:** `product_master.xlsx`를 DB 테이블로 승격하고, 카테고리별 마진율 기준으로 원가(`cost_price`)를 역산해 추가. 할인율/마진율 실시간 계산의 인프라로 사용.

**구현:**
- `scripts/add_cost_price.py` — 카테고리별 마진 배율 적용해 원가 계산 후 xlsx 저장 (체어 1.35배, 테이블 1.40배, 텐트 1.50배, 나머지 1.40배)
- `db.py` — product_master 테이블 신설 (product_code PK, list_price, cost_price)
- `scripts/seed_db.py` — `seed_product_master()` 추가, `seed()` 최초 실행 시 69건 적재
- `nodes/pattern_nodes.py` — `_discount_sensitivity()` 추가: daily_product + product_master 조인 → 할인율 역산 → 버킷별 집계 → 마진율 계산

**교훈:** 거래 데이터의 판매가는 이미 할인이 적용된 최종가라서, 할인율 역산에는 반드시 정가 마스터가 필요하다. product_master를 DB에 넣어두면 이후 버전(재고 시그널, 카니발리제이션 등)에서도 제품 단위 분석의 기준점으로 재사용할 수 있다.

---

### Decision 7: v1.5 할인율 역산 설계 — product_master 조인 방식 채택

**결정:** 할인율을 별도 컬럼으로 저장하지 않고, 거래가 ÷ 정가(product_master.list_price)로 매번 역산하는 방식을 채택한다.

**발견 과정:**
1. 샘플 ERP 데이터에 할인율 컬럼이 없음 확인
2. S/O sum 컬럼은 이미 할인이 적용된 최종가임을 확인 — 할인율 역산에 product_master 조인 필수

**구현:**
- `nodes/pattern_nodes.py` — `avg_sell_price = revenue / qty` → `discount_pct = (1 - avg_sell_price / list_price) * 100`
- `nodes/pattern_nodes.py` — qty = 0인 ZRE 전용 행 예외 처리 추가
- `nodes/pattern_nodes.py` — `_discount_sensitivity()`: 할인율 구간(bucket)별 집계, 마진율 계산, top_discounted 3개 추출

**교훈:** 거래 데이터에 할인율이 없어도 정가 마스터가 있으면 역산 가능하다. 단, qty가 0인 행(ZRE 전용)을 걸러내지 않으면 ZeroDivisionError가 발생한다. product_master 조인이 필요한 계산은 preprocess 단계가 아니라 pattern 단계에서 처리해야 state flow가 깔끔하다.

---

### Decision 6: v1.4 DB 오염 데이터 발견 및 재시딩

**결정:** `salescoach.db`를 삭제하고 `scripts/seed_db.py`로 91일치 데이터를 재적재한다.

**발견 과정:**
1. `SUM(total_revenue)` 조회 시 2026-06-04/05 매출이 정상 대비 100배(116억) 비정상 수치 확인
2. 같은 날짜의 6개 플랫폼 값이 완전 동일 → 중복 적재 의심
3. Streamlit 직접 업로드 테스트 시 날짜를 2026년으로 잘못 선택한 흔적으로 결론

**구현:**
- `salescoach.db` 삭제
- `scripts/seed_db.py` 재실행 — 2025-04-01 ~ 2025-06-30 (91일) 재적재

**교훈:** 개발 중 수동 테스트 데이터와 시딩 데이터가 같은 DB에 섞이면 디버깅이 오염된다. 테스트 날짜는 반드시 샘플 데이터 범위(2025-04-01~06-30) 안에서 선택해야 하며, 테스트 후 DB 상태를 정기적으로 확인하는 습관이 필요하다.

---

### Decision 5: v1.4 고객 코호트 → 구매 패턴 분석으로 피벗

**결정:** "고객 코호트 분석"에서 "거래(참조번호) 단위 구매 패턴 분석"으로 범위를 재정의한다.

**발견 과정:**
ERP 원본 데이터에 고객 식별자가 없어 신규/재구매 코호트 추적이 원천적으로 불가능함을 확인. 참조번호는 거래(주문) 단위 식별자라 동일 고객의 재방문을 구분할 방법이 없음.

**구현:**
- `nodes/pattern_nodes.py` — `_purchase_combo()` 추가: 거래별 Helinox+HCC 교차구매 비율, 카테고리 조합 TOP5
- `nodes/pattern_nodes.py` — `_basket_metrics()` 추가: 채널별 거래당 평균 아이템 수/금액
- `nodes/pattern_nodes.py` — `_time_pattern()` 추가: 오늘 요일 + 30일 요일별 평균 매출
- `nodes/pattern_nodes.py` — `_basket_association()` 추가: Support/Confidence 기반 연관 제품 쌍 TOP5
- `nodes/insight_node.py` — `_build_insight_context()`에 4개 섹션 추가, `_SYSTEM_PROMPT`에 판단 기준 3개 추가

**교훈:** 데이터가 지원하지 않는 분석을 억지로 설계하지 않고 가능한 범위로 좁히는 것이 장기적으로 신뢰도를 높인다. "고객 ID 없음"이라는 데이터 한계를 포트폴리오에서 정직하게 명시하는 것이 오히려 강점이 된다.

---

### Decision 4: v1.3 채팅 한계 명시 — NO_QUERY_POSSIBLE 가드

**결정:** `daily_product`/`daily_kpi`가 거래 단위가 아니므로 답할 수 없는 질문 유형을 LLM에게 명시하고, 그런 질문에는 SQL 대신 안내 메시지를 반환한다.

**발견 과정:**
1. "체어 사면 같이 사는 제품?" 질문에 LLM이 자기참조 서브쿼리(의미 없는 SQL)를 생성해 "조회된 데이터가 없습니다"로 잘못 답변
2. DB 스키마에 거래(영수증) 단위 식별자가 없어 연관구매 질문 자체가 불가능한 구조임을 확인
3. LLM이 "모른다"는 판단을 내리지 못하고 틀린 SQL을 만들어내는 것이 근본 원인으로 확정

**구현:**
- `nodes/qa_nodes.py` — `get_schema_context()`에 한계 규칙 6번 추가 (장바구니/연관구매/고객이력 질문에는 "NO_QUERY_POSSIBLE" 반환 지시)
- `nodes/qa_nodes.py` — `generate_sql()`에 NO_QUERY_POSSIBLE 반환 분기 추가
- `nodes/qa_nodes.py` — `answer_question()`에 NO_QUERY_POSSIBLE 감지 시 안내 메시지 반환 분기 추가

**교훈:** 스키마 기반 Text-to-SQL은 "이 데이터로 답할 수 있는 질문의 경계"를 명시하지 않으면 틀린 답을 그럴듯하게 만들어낸다. "모르면 모른다고 말하게" 만드는 가드레일도 가드레일의 일종이다.

---

### Decision 3: v1.3 SQL 생성 정확도 개선 — SUM 누락 + 테이블 선택 오류

**결정:** LLM이 SQL 생성 시 `SUM()`을 누락하거나 잘못된 테이블을 참조하는 문제를 스키마 가이드 강화와 few-shot 예시 추가로 해결한다.

**발견 과정:**
1. "전체 매출 얼마야?" → SUM 없이 단일 행만 반환, 결과값 비정상
2. "V.TARP 반품 몇 건?" → `daily_product`가 아닌 `daily_kpi`에서 조회, `zre` 컬럼명 오류

**구현:**
- `nodes/qa_nodes.py` — `get_schema_context()`에 5개 규칙 추가 (SUM 필수, 테이블 선택 기준, zre_qty 컬럼명, LIKE 부분일치, 기간 패턴)
- `nodes/qa_nodes.py` — `generate_sql()`에 few-shot 예시 3개 추가

**교훈:** Text-to-SQL에서 스키마만 주면 LLM이 집계 여부와 테이블 선택을 자주 틀린다. "이 테이블은 날짜당 여러 행이 존재하므로 SUM이 필요하다"는 맥락 설명과 few-shot 예시를 함께 줘야 정확도가 올라간다.

---

### Decision 2: v1.2 판단 레이어 신설 — 에이전트 정체성 확립

**결정:** rule-based 계산 → LLM 숫자 요약 구조에서, rule-based → insight(LLM 판단) → action(LLM 액션) → commentary(LLM 서술) 3단계 판단 레이어로 전환한다.

**구현:**
- `nodes/pattern_nodes.py` — 5개 패턴 계산 함수 신설 (channel_trends, category_movers, return_anomalies, forecast, promo_effect)
- `nodes/insight_node.py` — JSON 구조화 인사이트 노드 신설 (top_issue / risk_items / opportunity_items)
- `nodes/action_node.py` — 오늘/이번 주/이번 달 액션 3개 도출 노드 신설
- `graph.py` — 15노드로 재편, `SalesDailyState`에 patterns/insights/actions 필드 추가

**교훈:** "LLM이 숫자를 읽어주는 것"과 "LLM이 판단을 내리는 것"은 구조적으로 다른 설계를 요구한다. rule-based가 수치를 계산하고 LLM은 그 수치의 의미를 해석하는 역할 분리가 전제되어야 판단의 신뢰도가 생긴다.

---

### Decision 1: v1.2 날짜 필터링 + float64 정규화

**결정:** ERP 엑셀의 판매일자 컬럼이 `float64`로 로드될 때("20250525.0") `report_date` 필터가 실패하는 문제를 `_normalize_date_col()` 헬퍼로 수정한다.

**발견 과정:**
1. 날짜 필터 적용 후에도 매출이 0원으로 나옴
2. `preprocess` 함수 단독 실행은 정상(296행/618행) — 필터 단계 문제로 범위 좁힘
3. 판매일자 dtype 확인 → `float64`, `astype(str)` 시 "20250525.0" 형태로 변환되어 "20250525"와 불일치

**구현:**
- `nodes/preprocess_nodes.py` — `_normalize_date_col()` 헬퍼 추가: `pd.to_numeric → int → str.zfill(8)`으로 int/float/str 모두 안전하게 처리
- `nodes/preprocess_nodes.py` — 날짜 필터에 `.replace("-", "")` 추가로 하이픈 형식도 허용

**교훈:** pandas로 엑셀을 읽을 때 날짜처럼 보이는 숫자 컬럼은 `int64` 또는 `float64`로 로드된다. `astype(str)`만으로는 "20250525.0" 같은 float 표현이 나올 수 있어서, `to_numeric → int → str` 변환이 더 안전하다.
