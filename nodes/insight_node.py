import json
import logging
import os

from config import LLM_MAX_TOKENS, LLM_MODEL

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "당신은 리테일 비즈니스 매출 분석 전문가입니다.\n"
    "제공된 데이터에는 오늘 수치와 비교 기준값(7일 평균, 30일 평균, 월 목표)이 함께 있습니다.\n"
    "단순 요약이 아니라 '왜 이 숫자가 나왔는가', '무엇이 위험한가', '무엇이 기회인가'를 판단하세요.\n\n"
    "판단 기준:\n"
    "- 오늘 수치가 7일 평균보다 30% 이상 높으면 이유를 추론하세요\n"
    "- 반품률이 평균의 3배 이상이면 품질/CS 이슈로 분류하세요\n"
    "- 월말 예측 달성률이 80% 미만이면 위험 신호로 분류하세요\n"
    "- 특정 카테고리 집중도가 50% 초과면 편중 리스크로 분류하세요\n\n"
    "반드시 아래 JSON 형식으로만 응답하세요 (마크다운 코드블록 없이):\n"
    "{\n"
    '  "top_issue": "가장 시급한 이슈 한 문장 (구체적 수치 포함)",\n'
    '  "top_issue_reason": "왜 시급한지 근거 한 문장",\n'
    '  "forecast_summary": "월말 예측 한 문장 (달성률 % 포함)",\n'
    '  "trend_summary": "오늘 가장 주목할 추세 한 문장 (수치 포함)",\n'
    '  "promo_insight": "프로모션 효과 분석 (없으면 null)",\n'
    '  "risk_items": ["구체적 수치 포함한 리스크1", "리스크2"],\n'
    '  "opportunity_items": ["구체적 수치 포함한 기회1", "기회2"]\n'
    "}"
)


def _build_insight_context(state: dict) -> str:
    patterns = state.get("patterns", {})
    anomalies = state.get("anomalies", [])
    target_summary = state.get("target_summary", {})
    report_date = state.get("report_date", "")
    kpi_total = state.get("kpi_total", {})
    kpi_summary = state.get("kpi_summary", {})

    rd = (f"{report_date[:4]}-{report_date[4:6]}-{report_date[6:8]}"
          if len(report_date) >= 8 else report_date)

    lines = [f"[기준일: {rd}]", ""]

    # 오늘 전체 KPI (항상 포함)
    if kpi_total:
        lines.append("[오늘 전체 KPI]")
        lines.append(f"  총매출: {kpi_total.get('total_sales', 0):,}원")
        lines.append(f"  순영수증: {kpi_total.get('net_receipt', 0)}건")
        lines.append(f"  포인트: {kpi_total.get('total_point', 0):,}P")
        lines.append("")

    # 플랫폼별 매출 (항상 포함)
    by_platform = kpi_summary.get("by_platform", [])
    if by_platform:
        lines.append("[플랫폼별 매출]")
        for rec in by_platform:
            lines.append(
                f"  {rec['platform']}: {rec['total_sales']:,}원 "
                f"(ZOR {rec['zor']}건, ZRE {rec['zre']}건)"
            )
        lines.append("")

    # 채널 추세 (7일 평균 비교)
    trends = patterns.get("channel_trends", [])
    if trends:
        lines.append("[채널 추세 — 오늘 vs 7일 평균]")
        for t in trends:
            lines.append(
                f"  {t['channel']}: 오늘 {t['today']:,}원 / "
                f"7일 평균 {t['seven_day_avg']:,}원 / "
                f"변화율 {t['change_pct']:+.1f}% ({t['flag']})"
            )
        lines.append("")

    # 카테고리 집중도
    movers = patterns.get("category_movers", [])
    if movers:
        lines.append("[카테고리별 매출 비중]")
        for m in movers[:5]:
            flag_str = " ⚠️ 편중" if m["flag"] else ""
            lines.append(
                f"  {m['category_l1']}: {m['total_sales']:,}원 "
                f"({m['share_pct']}%){flag_str}"
            )
        lines.append("")

    # 반품 이상
    returns = patterns.get("return_anomalies", [])
    if returns:
        lines.append("[반품 이상 — 평균 대비 3배 초과 제품]")
        for r in returns:
            lines.append(
                f"  {r['product_name']}: "
                f"오늘 {r['return_rate_today']:.1%} / "
                f"30일 평균 {r['return_rate_avg']:.1%} / "
                f"평균의 {r['multiplier']}배"
            )
        lines.append("")
    else:
        lines.append("[반품 이상] 해당 없음")
        lines.append("")

    # 월말 예측
    fc = patterns.get("forecast", {})
    if fc:
        lines.append("[월말 예측]")
        lines.append(
            f"  이번달 현재 누적: {fc.get('current_total', 0):,}원"
        )
        lines.append(
            f"  일평균: {fc.get('daily_avg', 0):,}원 / "
            f"잔여 {fc.get('days_remaining', 0)}일"
        )
        lines.append(
            f"  예상 월말 매출: {fc.get('forecast_total', 0):,}원"
        )
        lines.append(
            f"  월 목표: {fc.get('target', 0):,}원 / "
            f"예상 달성률: {fc.get('forecast_achievement_pct', 0)}%"
        )
        lines.append("")

    # 타겟 달성 현황
    if target_summary:
        lines.append("[타겟 달성 현황]")
        lines.append(
            f"  전체: {target_summary.get('total_achievement_pct', 0)}% 달성 "
            f"({target_summary.get('total_actual', 0):,} / "
            f"{target_summary.get('total_target', 0):,}원), "
            f"잔여 {target_summary.get('days_remaining', 0)}일"
        )
        for pt in target_summary.get("by_platform", []):
            flag_str = " ⚠️ 저조" if pt.get("flag") == "low_achievement" else ""
            lines.append(
                f"  {pt['platform']}: {pt['achievement_pct']}%{flag_str} / "
                f"일평균 {pt['daily_required']:,}원 필요"
            )
        lines.append("")

    # 프로모션
    promo = patterns.get("promo_effect", {})
    if promo.get("active"):
        lines.append(
            f"[진행중 프로모션] {promo.get('name')}: "
            f"매출 리프트 {promo.get('sales_lift_pct', 0):+.1f}%"
        )
        lines.append("")

    # 이상치
    if anomalies:
        lines.append("[이상치 감지]")
        for a in anomalies:
            lines.append(
                f"  [{a.get('severity', '').upper()}] {a.get('message', '')}"
            )
        lines.append("")
    
    # by_product에서 반품 전용 항목 분리
    by_product = kpi_summary.get("by_product", [])
    return_only = [p for p in by_product if p["total_sales"] == 0 and p["zre_qty"] > 0]
    if return_only:
        lines.append("[오늘 반품만 발생한 제품 — 판매 없이 반품]")
        for p in return_only:
            lines.append(
                f"  {p['product_name']}: 반품 {p['zre_qty']}건 "
                f"(오늘 신규 판매 없음 — 이전 구매 반품)"
            )
        lines.append("")

    return "\n".join(lines)
    



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

        llm = ChatOpenAI(
            model=LLM_MODEL,
            max_tokens=LLM_MAX_TOKENS,
            api_key=api_key
        )
        response = llm.invoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt)
        ])
        raw = (response.content.strip()
               .removeprefix("```json")
               .removesuffix("```")
               .strip())
        insights = json.loads(raw)
        logger.info(
            f"insight_node 완료: top_issue={insights.get('top_issue', '')[:30]}..."
        )
    except Exception as e:
        logger.warning(f"insight_node 실패: {e}")
        errors.append(f"insight_node 실패: {e}")

    return {**state, "insights": insights, "errors": errors}