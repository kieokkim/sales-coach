import json
import logging
import os
import re

from config import LLM_MAX_TOKENS, LLM_MODEL
from nodes.context_builder import build_patterns_context

logger = logging.getLogger(__name__)

# 타겟 사용자·코칭 목적 정의: PERSONA.md 참고
_SYSTEM_PROMPT = (
    "당신은 리테일 비즈니스 매출 분석 전문가입니다.\n"
    "제공된 데이터에는 오늘 수치, 비교 기준값, 30일 장기 추세,\n"
    "요일/프로모션 보정이 적용된 일별 목표가 함께 있습니다.\n\n"

    "## 분석의 두 트랙\n"
    "트랙 A — 오늘의 신호 (top_issue, risk_items)\n"
    "  오늘 즉각 대응 가능한 이슈를 찾으세요.\n"
    "  '오늘 특별히 달라진 것'이어야 합니다.\n"
    "  매일 반복되는 구조적 특성(브랜드 편중 등)은 포함하지 마세요.\n\n"
    "트랙 B — 장기 흐름 (trend_summary, opportunity_items)\n"
    "  30일 추세와 가속도에서 보이는 방향성을 서술하세요.\n"
    "  우상향/우하향하는 큰 흐름을 놓치지 마세요.\n\n"

    "## top_issue 선택 우선순위 (트랙 A)\n"
    "1순위: 반품 이상\n"
    "  오늘 반품률이 30일 평균의 3배 이상이거나\n"
    "  판매 없이 반품만 집중 발생. 품질/CS 이슈 가능성.\n\n"
    "2순위: 수익성 이상\n"
    "  오늘 마진율 30% 미만. 할인이 수익을 훼손.\n"
    "  오늘 측정값이므로 즉각 확인 가능.\n\n"
    "3순위: 일별 목표 미달\n"
    "  오늘 순매출(반품 차감)이 요일/프로모션 보정 일별 목표의 80% 미만.\n"
    "  [조정 일별 목표] 섹션의 수치를 반드시 인용하세요.\n"
    "  월 누적 달성률(예: HCC 46%)은 top_issue가 아닌 risk_items에 포함.\n\n"
    "4순위: 추세 가속 하락\n"
    "  최근 7일이 직전 7일보다 15% 이상 하락. 하락 추세가 빨라지는 신호.\n\n"
    "※ 위 1~4순위 해당 없을 때만 구조적 특성 언급 가능.\n\n"

    "## 판단 기준\n"
    "- 반품률이 평균의 3배 이상이면 품질/CS 이슈로 분류\n"
    "- 이 회사 정상 마진은 약 28%입니다. 절대값이 낮은 것 자체는 이슈가 아닙니다\n"
    "- [할인/마진] 섹션의 '마진 편차'가 -3%p 이하면 수익성 이슈로 분류하세요\n"
    "  (오늘 판매 믹스로 기대되는 마진보다 실제가 낮다 = 할인/가격 훼손)\n"
    "- 오늘 순매출 < 조정 일별 목표 × 0.8이면 목표 미달로 분류\n"
    "  (단, 잔여일 < 7이면 × 0.6으로 완화)\n"
    "- 30일 추세 하락 + 가속하락이면 추세 악화로 분류\n"
    "- 교차구매 비율 30% 이상이면 브랜드 시너지 기회로 분류\n"
    "- 할인율 15% 이상 + 마진율 낮은 제품은 즉시 검토 대상\n\n"

    "## top_issue 작성 전 최종 체크 (반드시 통과해야 함)\n"
    "- top_issue 문장에 '월', '누적', '달성률'이라는 단어가 들어가면서\n"
    "  동시에 특정 채널명(HCC 등)만 언급한다면, 그것은 트랙 A가 아니라\n"
    "  risk_items 대상입니다. top_issue에서 제외하고 risk_items로 옮기세요.\n"
    "- [조정 일별 목표] 섹션에 오늘 수치가 있다면, 채널별 월 누적 수치보다\n"
    "  이것을 우선하세요. '오늘' 수치가 없으면 목표 관련 이슈는 아예\n"
    "  top_issue 후보에서 제외하고 risk_items로만 다루세요.\n\n"

    "반드시 아래 JSON 형식으로만 응답하세요 (마크다운 코드블록 없이):\n"
    "{\n"
    '  "top_issue": "오늘 가장 시급한 이슈 (구체적 수치, 구조적 특성 제외)",\n'
    '  "top_issue_reason": "왜 시급한지 — 7일/30일 평균 또는 조정 목표와 비교",\n'
    '  "forecast_summary": "월말 예측 달성률 % 포함 한 문장",\n'
    '  "trend_summary": "30일 방향성 + 가속도 포함 한 문장",\n'
    '  "promo_insight": "프로모션 효과 분석 (없으면 null)",\n'
    '  "risk_items": ["채널별 달성률 저조 등 오늘 당장 못 바꾸는 리스크", "..."],\n'
    '  "opportunity_items": ["오늘 데이터 기반 기회", "..."]\n'
    "}"
)


def _load_company_profile() -> str:
    """COMPANY_PROFILE.md를 읽어서 프롬프트에 포함할 텍스트로 반환."""
    profile_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "COMPANY_PROFILE.md"
    )
    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def _build_insight_context(state: dict) -> str:
    return build_patterns_context(state)


_MONTHLY_CUMULATIVE_PATTERN = re.compile(
    r"(월\s*(누적|달성률)|누적\s*달성률)"
)
_CHANNEL_NAMES = ["HCC", "메이크샵", "네이버", "카카오", "부산점", "제주점"]


def _is_monthly_cumulative_issue(top_issue: str) -> bool:
    """
    top_issue가 '월 누적 달성률 + 특정 채널명' 패턴인지 판정한다.
    이 패턴은 트랙A(오늘 즉각 대응) 자격이 없다 — 매일 거의 안 바뀌는
    월 누적 수치이기 때문이다. 프롬프트 지시로 반복 실패했으므로
    rule-based로 강제 격리한다.
    """
    if not top_issue:
        return False
    has_monthly_keyword = bool(_MONTHLY_CUMULATIVE_PATTERN.search(top_issue))
    has_channel_name = any(ch in top_issue for ch in _CHANNEL_NAMES)
    return has_monthly_keyword and has_channel_name


def _enforce_track_a_isolation(insights: dict, patterns: dict) -> dict:
    """
    insights['top_issue']가 월 누적+채널 패턴이면 risk_items로 옮기고
    다음으로 유효한 트랙A 신호(반품 이상 > 마진 편차 > 목표 페이스)로 대체한다.
    """
    top_issue = insights.get("top_issue", "")
    if not _is_monthly_cumulative_issue(top_issue):
        return insights

    risk_items = list(insights.get("risk_items") or [])
    risk_items.insert(0, top_issue)
    insights["risk_items"] = risk_items

    return_anomalies = patterns.get("return_anomalies", [])
    discount = patterns.get("discount_sensitivity", {})
    adt = patterns.get("adjusted_daily_target", {})

    if return_anomalies:
        r = return_anomalies[0]
        insights["top_issue"] = (
            f"{r['product_name']} 반품률 이상 — "
            f"오늘 {r['return_rate_today']:.1%}, 평균의 {r['multiplier']}배"
        )
    elif discount.get("margin_deviation") is not None and discount["margin_deviation"] <= -3:
        insights["top_issue"] = (
            f"오늘 마진이 판매 믹스 기대치보다 "
            f"{abs(discount['margin_deviation'])}%p 낮음 — 할인/가격 이슈 추정"
        )
    elif adt.get("severity") in ("high", "medium", "low") and adt.get("achievement_vs_adjusted") is not None:
        insights["top_issue"] = (
            f"오늘 순매출이 조정 일별 목표의 "
            f"{adt['achievement_vs_adjusted']}%에 불과 — 목표 페이스 미달"
        )
    else:
        insights["top_issue"] = "오늘 특이 이슈 없음 — 정상 범위"
        insights["top_issue_reason"] = "반품/마진/목표 페이스 모두 정상 범위 내"

    return insights


def insight_node(state: dict) -> dict:
    errors = list(state.get("errors", []))
    insights: dict = {}

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        logger.warning("OPENAI_API_KEY 미설정, insight_node 스킵")
        return {**state, "insights": insights, "errors": errors}

    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage

        context = _build_insight_context(state)
        report_date = state.get("report_date", "")
        rd = (f"{report_date[:4]}-{report_date[4:6]}-{report_date[6:8]}"
              if len(report_date) >= 8 else report_date)

        user_prompt = (
            f"[분석 기준일: {rd}]\n\n"
            f"아래 데이터를 바탕으로 비즈니스 인사이트를 도출하세요.\n"
            f"각 수치가 '많은지 적은지'는 비교 기준값(7일 평균, 30일 평균, 월 목표)을 "
            f"반드시 참조하여 판단하세요:\n\n"
            f"{context}"
        )

        company_profile = _load_company_profile()
        if company_profile:
            system_prompt = (
                "## 기업/도메인 특성 (판단 시 반드시 참조)\n"
                f"{company_profile}\n\n"
                "---\n\n"
                + _SYSTEM_PROMPT
            )
        else:
            system_prompt = _SYSTEM_PROMPT

        llm = ChatOpenAI(
            model=LLM_MODEL,
            max_tokens=LLM_MAX_TOKENS,
            api_key=api_key
        )
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ])
        raw = (response.content.strip()
               .removeprefix("```json")
               .removesuffix("```")
               .strip())
        raw = re.sub(r',\s*([}\]])', r'\1', raw)
        insights = json.loads(raw)
        insights = _enforce_track_a_isolation(insights, state.get("patterns", {}))
        logger.info(
            f"insight_node 완료: top_issue={insights.get('top_issue', '')[:30]}..."
        )
    except Exception as e:
        logger.warning(f"insight_node 실패: {e}")
        errors.append(f"insight_node 실패: {e}")

    return {**state, "insights": insights, "errors": errors}