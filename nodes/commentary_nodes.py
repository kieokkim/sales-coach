import logging
import os

from config import LLM_MAX_TOKENS, LLM_MODEL, PROMOTIONS

logger = logging.getLogger(__name__)


def _is_promotion_period(report_date: str) -> list[str]:
    if len(report_date) < 8:
        return []
    year = report_date[:4]
    month = report_date[4:6]
    month_key = f"{year}-{month}"
    active = []
    for promo in PROMOTIONS.get(month_key, []):
        if promo["start"] <= report_date <= promo["end"]:
            active.append(promo["name"])
    return active


def _build_context(state: dict) -> str:
    kpi_records = state.get("kpi_summary", {}).get("by_platform", [])
    kpi_total = state.get("kpi_total", {})
    target_summary = state.get("target_summary", {})
    anomalies = state.get("anomalies", [])
    report_date = state.get("report_date", "")

    lines = [f"[기준일: {report_date}]", ""]

    lines.append("[플랫폼별 KPI]")
    for rec in kpi_records:
        lines.append(
            f"  {rec['platform']}: 순영수증 {rec['net_receipt']}건, "
            f"매출 {rec['total_sales']:,}원, 포인트 {rec['total_point']:,}점"
        )
    lines.append(
        f"  전체 합계: 순영수증 {kpi_total.get('net_receipt', 0)}건, "
        f"매출 {kpi_total.get('total_sales', 0):,}원"
    )
    lines.append("")

    if target_summary:
        lines.append("[타겟 달성 현황]")
        lines.append(
            f"  전체: {target_summary.get('total_achievement_pct', 0)}% "
            f"({target_summary.get('total_actual', 0):,} / {target_summary.get('total_target', 0):,}원), "
            f"남은 {target_summary.get('days_remaining', 0)}일"
        )
        for pt in target_summary.get("by_platform", []):
            flag_str = " ⚠️ 저조" if pt.get("flag") == "low_achievement" else ""
            lines.append(
                f"  {pt['platform']}: {pt['achievement_pct']}%"
                f"{flag_str}, 일평균 {pt['daily_required']:,}원 필요"
            )
        lines.append("")

    if anomalies:
        lines.append("[이상치]")
        for a in anomalies:
            lines.append(f"  [{a['severity'].upper()}] {a['message']}")
        lines.append("")

    # 중분류별 매출 TOP5
    by_category = state.get("kpi_summary", {}).get("by_category", [])
    if by_category:
        l2_map: dict = {}
        for item in by_category:
            l2 = item["category_l2"]
            if l2 not in l2_map:
                l2_map[l2] = {
                    "category_l1": item["category_l1"],
                    "category_l2": l2,
                    "total_sales": 0,
                    "qty": 0,
                }
            l2_map[l2]["total_sales"] += item["total_sales"]
            l2_map[l2]["qty"] += item["qty"]
        top_l2 = sorted(l2_map.values(), key=lambda x: x["total_sales"], reverse=True)[:5]
        lines.append("[중분류별 매출 TOP5]")
        for item in top_l2:
            lines.append(
                f"  {item['category_l2']} ({item['category_l1']}): "
                f"{item['total_sales']:,}원 / {item['qty']}개"
            )
        lines.append("")

    # 오늘 제품 TOP5 + 반품 이상 징후
    by_product = state.get("kpi_summary", {}).get("by_product", [])
    if by_product:
        lines.append("[오늘 판매 TOP5 제품]")
        for prod in by_product[:5]:
            zre_note = f" ⚠️ 반품 {prod['zre_qty']}건" if prod["zre_qty"] > 0 else ""
            lines.append(
                f"  {prod['product_name']}: {prod['total_sales']:,}원 "
                f"({prod['qty']}개){zre_note}"
            )
        lines.append("")

    # 최근 30일 누적 TOP5 제품
    top_30d = state.get("kpi_cumulative", {}).get("top_products_30d", [])
    if top_30d:
        lines.append("[최근 30일 누적 TOP5 제품]")
        for prod in top_30d[:5]:
            lines.append(
                f"  {prod['product_name']}: {prod['total_revenue']:,}원 "
                f"(누적 {prod['total_qty']}개, 반품 {prod['total_zre']}건)"
            )
        lines.append("")

    # AI 인사이트 분석
    insights = state.get("insights", {})
    if insights:
        lines.append("[AI 인사이트 분석]")
        if insights.get("top_issue"):
            lines.append(f"  핵심 이슈: {insights['top_issue']}")
        if insights.get("top_issue_reason"):
            lines.append(f"  근거: {insights['top_issue_reason']}")
        if insights.get("forecast_summary"):
            lines.append(f"  월말 예측: {insights['forecast_summary']}")
        if insights.get("trend_summary"):
            lines.append(f"  주목 추세: {insights['trend_summary']}")
        if insights.get("promo_insight"):
            lines.append(f"  프로모션: {insights['promo_insight']}")
        for r in insights.get("risk_items", []):
            lines.append(f"  ⚠️ 리스크: {r}")
        for o in insights.get("opportunity_items", []):
            lines.append(f"  ✅ 기회: {o}")
        lines.append("")

    # 오늘 반품만 발생한 제품 (ZOR=0, ZRE>0)
    by_product_all = state.get("kpi_summary", {}).get("by_product", [])
    return_only = [p for p in by_product_all if p["total_sales"] == 0 and p["zre_qty"] > 0]
    if return_only:
        lines.append("[오늘 반품만 발생한 제품 — 즉각 확인 필요]")
        for p in return_only:
            lines.append(
                f"  {p['product_name']}: 반품 {p['zre_qty']}건 "
                f"(오늘 신규 판매 없음, 이전 구매 반품 집중)"
            )
        lines.append("")

    patterns = state.get("patterns", {})
    discount = patterns.get("discount_sensitivity", {})
    if discount.get("bucket_summary"):
        lines.append("[할인율별 판매 + 마진 현황]")
        lines.append(
            f"  오늘 전체 마진율: {discount.get('margin_pct_overall', 0)}% "
            f"(마진 총액 {discount.get('total_margin', 0):,}원)"
        )
        for bucket, m in discount["bucket_summary"].items():
            lines.append(
                f"  할인 {bucket}: 제품 {m['product_count']}개, "
                f"평균 판매량 {m['avg_qty']}개"
            )
        top = discount.get("top_discounted", [])
        if top:
            lines.append("  최대 할인 제품 TOP3 (마진율 포함):")
            for t in top[:3]:
                lines.append(
                    f"    {t['product_name']}: {t['discount_pct']}% 할인, "
                    f"마진율 {t['margin_pct']}%, {t['qty']}개 판매"
                )
        lines.append("")

    actions = state.get("actions", [])
    if actions:
        lines.append("[권장 액션]")
        for a in actions:
            lines.append(
                f"  [{a.get('timing', '')}] {a.get('owner', '')}: {a.get('action', '')}"
            )
        lines.append("")

    active_promos = _is_promotion_period(report_date)
    if active_promos:
        lines.append(f"[진행 중인 프로모션] {', '.join(active_promos)}")
        lines.append("")

    return "\n".join(lines)


def commentary_node(state: dict) -> dict:
    errors = list(state.get("errors", []))
    llm_commentary = ""

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        logger.warning("OPENAI_API_KEY 미설정, LLM 코멘터리 생략")
        return {**state, "llm_commentary": llm_commentary, "errors": errors}

    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage

        context = _build_context(state)
        report_date = state.get("report_date", "")
        rd = f"{report_date[:4]}-{report_date[4:6]}-{report_date[6:8]}" if len(report_date) >= 8 else report_date
        # 타겟 사용자·코칭 목적 정의: PERSONA.md 참고
        system_prompt = (
            f"오늘 날짜는 {rd}입니다.\n"
            "당신은 리테일 비즈니스 매출 분석 어시스턴트입니다.\n"
            "제공된 데이터의 [AI 인사이트 분석]과 [권장 액션]을 반드시 코멘터리에 반영하세요.\n\n"
            "작성 규칙:\n"
            "- 첫 문장은 반드시 오늘의 핵심 이슈 한 줄 요약 (구체적 수치 포함)\n"
            "- 결론을 먼저, 근거를 나중에\n"
            "- 반품 이상이 있으면 반드시 제품명과 건수를 명시\n"
            "- 마지막 문장은 반드시 가장 시급한 액션 (담당자 + 행동 명시)\n"
            "- 5~7문장, 수치는 제공된 데이터만 인용, 마크다운 없이 순수 텍스트\n"
            "- 모호한 표현('검토가 필요합니다') 금지\n"
            "- 마진율이 30% 미만이면 수익성 문제를 명시적으로 언급하세요\n"
            "- 할인율이 높은데 마진율도 낮은 제품은 즉시 검토 대상으로 지적하세요\n"
        )
        user_prompt = (
            f"[분석 기준일: {rd}]\n\n"
            f"아래 데이터의 [AI 인사이트 분석]과 [권장 액션] 섹션을 "
            f"반드시 코멘터리에 반영하세요:\n\n{context}"
        )

        llm = ChatOpenAI(model=LLM_MODEL, max_tokens=LLM_MAX_TOKENS, api_key=api_key)
        response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
        llm_commentary = response.content.strip()
        logger.info("LLM 코멘터리 생성 완료")
    except Exception as e:
        logger.warning(f"LLM 코멘터리 생성 실패: {e}")
        errors.append(f"LLM 코멘터리 생성 실패: {e}")

    return {**state, "llm_commentary": llm_commentary, "errors": errors}
