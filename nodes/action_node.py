import json
import logging
import os

from config import LLM_MAX_TOKENS, LLM_MODEL

logger = logging.getLogger(__name__)

# 타겟 사용자·코칭 목적 정의: PERSONA.md 참고
_SYSTEM_PROMPT = (
    "당신은 리테일 영업/마케팅 매니저의 어시스턴트입니다.\n"
    "인사이트를 바탕으로 구체적이고 실행 가능한 액션을 도출하세요.\n\n"
    "규칙:\n"
    "- 반드시 JSON 형식으로만 응답하세요\n"
    "- 마크다운 코드블록 없이 순수 JSON만 출력하세요\n"
    "- 액션은 반드시 담당자가 오늘 당장 실행할 수 있는 수준으로\n"
    '- 모호한 표현("검토가 필요합니다") 금지\n'
    "- 한국어로 작성하세요\n"
    "- scope: 이 액션으로 해결 가능한 범위를 명시하세요. "
    "본사/매장 차원에서 실행 가능한 것과, 제조/공급망 등 더 큰 범위가 "
    "필요한 것을 구분하세요\n"
    "- expected_impact: 이 액션을 실행했을 때 기대되는 효과를 "
    "제공된 데이터 근거(반품률, 교차구매율, 마진율 등)와 함께 "
    "구체적으로 서술하세요. 막연한 기대가 아니라 수치 근거가 있어야 합니다"
)

_ACTION_FORMAT = (
    '{"actions": ['
    '{"timing": "오늘 즉시", "owner": "...", "action": "...", "reason": "...", '
    '"scope": "...", "expected_impact": "..."}, '
    '{"timing": "이번 주", "owner": "...", "action": "...", "reason": "...", '
    '"scope": "...", "expected_impact": "..."}, '
    '{"timing": "이번 달", "owner": "...", "action": "...", "reason": "...", '
    '"scope": "...", "expected_impact": "..."}'
    "]}"
)


def _build_action_context(state: dict) -> str:
    insights = state.get("insights", {})
    patterns = state.get("patterns", {})
    target_summary = state.get("target_summary", {})
    kpi_summary = state.get("kpi_summary", {})
    lines = []

    if insights:
        lines.append("[인사이트]")
        if insights.get("top_issue"):
            lines.append(f"  핵심 이슈: {insights['top_issue']}")
        if insights.get("top_issue_reason"):
            lines.append(f"  근거: {insights['top_issue_reason']}")
        if insights.get("forecast_summary"):
            lines.append(f"  월말 예측: {insights['forecast_summary']}")
        if insights.get("trend_summary"):
            lines.append(f"  추세: {insights['trend_summary']}")
        risks = insights.get("risk_items", [])
        if risks:
            lines.append(f"  리스크: {', '.join(risks)}")
        opps = insights.get("opportunity_items", [])
        if opps:
            lines.append(f"  기회: {', '.join(opps)}")
        lines.append("")

    returns = patterns.get("return_anomalies", [])
    if returns:
        lines.append("[반품 이상 제품 — 평균 대비 3배 초과]")
        for r in returns:
            lines.append(
                f"  {r['product_name']}: 오늘 {r['return_rate_today']:.1%} "
                f"/ 30일 평균의 {r['multiplier']}배"
            )
        lines.append("")

    by_product = kpi_summary.get("by_product", [])
    return_only = [p for p in by_product if p["total_sales"] == 0 and p["zre_qty"] > 0]
    if return_only:
        lines.append("[오늘 반품만 발생한 제품 — 이전 구매 반품]")
        for p in return_only:
            lines.append(
                f"  {p['product_name']}: 반품 {p['zre_qty']}건 "
                f"(오늘 신규 판매 없음, 이전 구매 반품 집중)"
            )
        lines.append("")

    fc = patterns.get("forecast", {})
    if fc:
        lines.append(
            f"[월말 예측] 예상 달성률 {fc.get('forecast_achievement_pct', 0)}% / "
            f"잔여 {fc.get('days_remaining', 0)}일"
        )
        lines.append("")

    if target_summary and target_summary.get("total_target", 0) > 0:
        lines.append(
            f"[목표 달성률] {target_summary.get('total_achievement_pct', 0)}% "
            f"(잔여 {target_summary.get('days_remaining', 0)}일)"
        )
        for pt in target_summary.get("by_platform", []):
            if pt.get("flag") == "low_achievement":
                lines.append(
                    f"  ⚠️ {pt['platform']}: {pt['achievement_pct']}% 저조 / "
                    f"일평균 {pt['daily_required']:,}원 필요"
                )
        lines.append("")

    return "\n".join(lines) if lines else "인사이트 데이터 없음"


def action_node(state: dict) -> dict:
    errors = list(state.get("errors", []))
    actions: list = []

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        logger.warning("OPENAI_API_KEY 미설정, action_node 스킵")
        return {**state, "actions": actions, "errors": errors}

    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage

        context = _build_action_context(state)
        user_prompt = (
            "다음 인사이트와 데이터를 바탕으로 오늘/이번 주/이번 달 액션 3개를 도출하세요:\n\n"
            f"{context}\n\n"
            f"JSON 형식:\n{_ACTION_FORMAT}"
        )

        llm = ChatOpenAI(model=LLM_MODEL, max_tokens=LLM_MAX_TOKENS, api_key=api_key)
        response = llm.invoke([SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=user_prompt)])
        raw = response.content.strip().removeprefix("```json").removesuffix("```").strip()
        parsed = json.loads(raw)
        actions = parsed.get("actions", [])
        logger.info(f"action_node 완료: {len(actions)}개 액션")
    except Exception as e:
        logger.warning(f"action_node 실패: {e}")
        errors.append(f"action_node 실패: {e}")

    return {**state, "actions": actions, "errors": errors}
