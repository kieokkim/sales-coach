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
    "- 마진율 30% 미만이면 수익성 위험으로 분류\n"
    "- 오늘 순매출 < 조정 일별 목표 × 0.8이면 목표 미달로 분류\n"
    "  (단, 잔여일 < 7이면 × 0.6으로 완화)\n"
    "- 30일 추세 하락 + 가속하락이면 추세 악화로 분류\n"
    "- 교차구매 비율 30% 이상이면 브랜드 시너지 기회로 분류\n"
    "- 할인율 15% 이상 + 마진율 낮은 제품은 즉시 검토 대상\n\n"

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
        raw = re.sub(r',\s*([}\]])', r'\1', raw)
        insights = json.loads(raw)
        logger.info(
            f"insight_node 완료: top_issue={insights.get('top_issue', '')[:30]}..."
        )
    except Exception as e:
        logger.warning(f"insight_node 실패: {e}")
        errors.append(f"insight_node 실패: {e}")

    return {**state, "insights": insights, "errors": errors}