import json
import logging
import os

from config import LLM_MAX_TOKENS, LLM_MODEL
from nodes.context_builder import build_patterns_context

logger = logging.getLogger(__name__)

# 타겟 사용자·코칭 목적 정의: PERSONA.md 참고
_SYSTEM_PROMPT = (
    "당신은 리테일 비즈니스 매출 분석 전문가입니다.\n"
    "제공된 데이터에는 오늘 수치와 비교 기준값(7일 평균, 30일 평균, 월 목표)이 함께 있습니다.\n"
    "단순 요약이 아니라 '왜 이 숫자가 나왔는가', '무엇이 위험한가', '무엇이 기회인가'를 판단하세요.\n\n"
    "판단 기준:\n"
    "- 오늘 수치가 7일 평균보다 30% 이상 높으면 이유를 추론하세요\n"
    "- 반품률이 평균의 3배 이상이면 품질/CS 이슈로 분류하세요\n"
    "- 월말 예측 달성률이 80% 미만이면 위험 신호로 분류하세요\n"
    "- 특정 카테고리 집중도가 50% 초과면 편중 리스크로 분류하세요\n"
    "- 교차구매 비율이 30% 이상이면 브랜드 시너지 기회로 분류하세요\n"
    "- 특정 요일이 30일 평균보다 현저히 다르면 요일 패턴 이슈로 분류하세요\n"
    "- 장바구니 연관 신뢰도가 20% 이상인 조합은 묶음 프로모션 기회로 분류하세요\n"
    "- 전체 마진율이 30% 미만이면 수익성 위험으로 분류하세요\n"
    "- 할인율 15% 이상이면서 마진율도 낮은 제품은 즉시 검토 대상으로 지적하세요\n\n"
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
    return build_patterns_context(state)

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