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
        system_prompt = (
            f"오늘 날짜는 {rd}입니다. 반드시 이 날짜를 기준으로 작성하세요. "
            f"임의로 날짜를 추론하거나 변경하지 마세요.\n"
            "당신은 리테일 비즈니스 매출 분석 어시스턴트입니다. "
            "수치는 제공된 데이터만 인용하고 직접 계산하지 마세요. "
            "3~5문장, 비즈니스 리포트 어조로, 마크다운 없이 순수 텍스트로 작성하세요."
        )
        user_prompt = (
            f"[분석 기준일: {rd}] 이 날짜를 반드시 사용하세요.\n\n"
            f"다음 판매 데이터를 바탕으로 오늘의 매출 현황을 요약해주세요:\n\n{context}"
        )

        llm = ChatOpenAI(model=LLM_MODEL, max_tokens=LLM_MAX_TOKENS, api_key=api_key)
        response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
        llm_commentary = response.content.strip()
        logger.info("LLM 코멘터리 생성 완료")
    except Exception as e:
        logger.warning(f"LLM 코멘터리 생성 실패: {e}")
        errors.append(f"LLM 코멘터리 생성 실패: {e}")

    return {**state, "llm_commentary": llm_commentary, "errors": errors}
