import logging
import os

from config import LLM_MAX_TOKENS, LLM_MODEL, PROMOTIONS
from nodes.context_builder import build_patterns_context

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
    return build_patterns_context(state)

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
