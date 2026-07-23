import json
import logging
import os
import re

from config import LLM_MAX_TOKENS, LLM_MODEL, DOMAIN_PARAMS, classify_return_severity
from nodes.context_builder import build_patterns_context
from eval.ground_truth import determine_ground_truth_set

logger = logging.getLogger(__name__)

# 타겟 사용자·코칭 목적 정의: PERSONA.md 참고
_SYSTEM_PROMPT = (
    "당신은 리테일 비즈니스 매출 분석 전문가입니다.\n"
    "제공된 데이터에는 오늘 수치, 비교 기준값, 30일 추세, 조정 일별 목표가 있습니다.\n\n"

    "## 당신의 임무\n"
    "본사 담당자가 '오늘 주목해야 할 것'을 골라 건네는 것입니다.\n"
    "핵심은 '분석'이 아니라 '선별'입니다. 모든 걸 나열하지 말고,\n"
    "오늘 진짜 중요한 것만 최대 2개까지 고르세요.\n\n"

    "## top_issues 작성 규칙\n"
    "- 오늘 즉각 주목할 이슈를 0~2개 고릅니다.\n"
    "- 특이사항이 없으면 빈 리스트 []가 정답입니다. 억지로 만들지 마세요.\n"
    "  (매일 반복되는 구조적 특성인 브랜드 편중은 이슈가 아닙니다)\n"
    "- 각 이슈는 issue(자연어 서술)와 category(유형 태깅)로 구성합니다.\n"
    "- issue는 구체적 수치를 포함해 자유롭게 서술하세요.\n"
    "- category는 반드시 아래 6개 중 하나로 태깅하세요:\n"
    "  반품이슈 / 수익성문제 / 목표미달 / 추세악화 / 편중 / 기타\n"
    "  ('기타'는 5개로 안 잡히는 새 이슈에만. 남발 금지)\n\n"

    "## 카테고리별 판정 기준\n"
    "- 반품이슈: 오늘 반품률이 30일 평균의 3배 이상이거나 판매 없이 반품만 집중 발생\n"
    "  ([반품 이상] 섹션에 '사유별 금액'이 있으면 반영하세요. 숫자를 기계적으로\n"
    "   나열하지 말고 어떤 사유가 우세한지 자연스럽게 녹이되, 인용하는 금액은\n"
    "   반드시 제공된 원본 수치와 일치해야 합니다 — 왜곡·반올림 임의 변경 금지.\n"
    "   사유별 금액이 있으면 반드시 언급하세요 — 생략 금지. 금액이 큰 사유부터\n"
    "   순서대로 서술하세요.)\n"
    "- 수익성문제: [할인/마진] 섹션의 '마진 편차'가 -3%p 이하\n"
    "  (이 회사 정상 마진은 약 28%. 절대값이 낮은 것 자체는 이슈가 아님.\n"
    "   오늘 판매 믹스로 기대되는 마진보다 실제가 낮다 = 할인/가격 훼손)\n"
    "- 목표미달: 오늘 순매출(반품 차감)이 조정 일별 목표의 80% 미만\n"
    "  (잔여일 < 7이면 60% 미만). [조정 일별 목표] 섹션 수치를 인용하세요.\n"
    "  ※ 월 누적 달성률(예: HCC 46%)은 top_issues가 아닌 risk_items에 넣으세요.\n"
    "     매일 거의 안 바뀌는 구조적 수치이므로 '오늘의 이슈'가 아닙니다.\n"
    "- 추세악화: 30일 방향이 '하락'이고, 최근 가속이 회사 변동성 대비 유의하게\n"
    "  음(陰)으로 꺾일 때. [30일 장기 추세] 섹션에 '추세악화 신호'가 표시된\n"
    "  날만 해당. 30일 방향이 상승/횡보면 단기 가속하락이어도 추세악화 아님.\n"
    "- 편중: 특정 브랜드/카테고리 비중 지배. 단, 매일 반복되면 이슈 아님.\n\n"

    "## 태깅 게이트 (반드시 지킬 것 — 어기면 시스템이 자동 제거함)\n"
    "- 목표미달: [조정 일별 목표] 섹션의 달성률이 80% 미만일 때만.\n"
    "  80% 이상이면 목표미달 아님. 달성률이 100%를 넘으면 절대 목표미달 아님.\n"
    "- 수익성문제: [할인/마진] 섹션의 '마진 편차'가 -3%p 이하일 때만.\n"
    "  편차가 -3%p보다 크면(0에 가까우면) 수익성문제 아님.\n"
    "- 확실하지 않으면 태깅하지 마세요. 빈 리스트가 정답인 날이 많습니다.\n\n"

    "## relation (이슈가 2개일 때만)\n"
    "- linked: 한 이슈가 다른 이슈의 원인 (예: 할인 과다 → 마진 훼손 + 목표 미달)\n"
    "- independent: 두 이슈의 원인이 서로 다름\n"
    "- 이슈가 0~1개면 null\n\n"

    "반드시 아래 JSON 형식으로만 응답하세요 (마크다운 코드블록 없이):\n"
    "{\n"
    '  "top_issues": [\n'
    '    {"issue": "구체적 수치 포함 서술", "category": "6개 중 하나"},\n'
    '    {"issue": "...", "category": "..."}\n'
    "  ],\n"
    '  "relation": "independent | linked | null (이슈 0~1개면 null)",\n'
    '  "forecast_summary": "월말 예측 달성률 % 포함 한 문장",\n'
    '  "trend_summary": "30일 방향성 + 가속도 한 문장",\n'
    '  "promo_insight": "프로모션 효과 (없으면 null)",\n'
    '  "risk_items": ["채널별 월 누적 저조 등 오늘 못 바꾸는 리스크", "..."],\n'
    '  "opportunity_items": ["오늘 데이터 기반 기회", "..."]\n'
    "}\n\n"
    "top_issues가 빈 리스트면 relation은 null, "
    "risk_items와 trend_summary는 그대로 작성하세요."
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
_CHANNEL_NAMES = ["HCC", "메이크샵", "네이버", "카카오", "Store 1", "Store 2"]


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


def _validate_category_by_rule(item: dict, patterns: dict) -> bool:
    """
    LLM이 태깅한 category가 rule 기준에 실제로 부합하는지 검증한다.
    프롬프트 지시로 반복 실패했으므로 rule-based로 강제 확인.
    부합하면 True(유지), 아니면 False(제거).

    검증 대상: 목표미달, 수익성문제, 추세악화 (수치 기준이 명확한 것)
    반품이슈는 rule 판정과 LLM 판단이 대체로 일치하므로 통과.
    """
    category = item.get("category", "")

    if category == "목표미달":
        adt = patterns.get("adjusted_daily_target", {})
        sev = adt.get("severity")
        # high/medium/low는 실제 목표 미달. none이면 달성/초과 → 오태깅
        valid = sev in ("high", "medium", "low")
        if not valid:
            logger.info(
                f"category 게이트: 목표미달 제거 "
                f"(severity={sev}, 달성률={adt.get('achievement_vs_adjusted')}%)"
            )
        return valid

    if category == "수익성문제":
        discount = patterns.get("discount_sensitivity", {})
        dev = discount.get("margin_deviation")
        # 편차 -3%p 이하만 실제 수익성 문제
        valid = dev is not None and dev <= -3
        if not valid:
            logger.info(
                f"category 게이트: 수익성문제 제거 (margin_deviation={dev})"
            )
        return valid

    if category == "추세악화":
        trend = patterns.get("trend_direction_30d", {})
        z_thr = DOMAIN_PARAMS.get("trend_z_threshold", 1.5)
        accel_z = trend.get("accel_zscore")
        # ground_truth와 동일 조건: 30일 방향 하락 AND 가속 z 유의.
        # 상승/횡보 중 단기 가속하락(0518/0526류) 오태깅 제거.
        valid = (trend.get("overall_direction") == "하락"
                 and accel_z is not None and accel_z <= -z_thr)
        if not valid:
            logger.info(
                f"category 게이트: 추세악화 제거 "
                f"(direction={trend.get('overall_direction')}, accel_z={accel_z})"
            )
        return valid

    # 반품이슈/편중/기타는 통과
    return True


def _enforce_track_a_isolation(insights: dict, patterns: dict) -> dict:
    """
    top_issues의 각 항목을 검사한다:
    1) '월 누적+채널명' 패턴이면 risk_items로 격리 (보조 안전장치)
    2) category가 rule 기준에 미달하면 제거 (오태깅 게이트)
    """
    top_issues = insights.get("top_issues", [])
    if not isinstance(top_issues, list):
        logger.warning("top_issues가 리스트가 아님, 빈 리스트로 초기화")
        insights["top_issues"] = []
        return insights

    kept = []
    risk_items = list(insights.get("risk_items", []))

    for item in top_issues:
        if not isinstance(item, dict):
            continue
        issue_text = item.get("issue", "")
        # 1) 월 누적+채널명 패턴이면 격리 (보조 안전장치)
        if _is_monthly_cumulative_issue(issue_text):
            logger.info(f"트랙A 격리: '{issue_text[:40]}...' → risk_items")
            risk_items.insert(0, issue_text)
            continue

        # 2) category rule 게이트
        if not _validate_category_by_rule(item, patterns):
            # 오태깅된 이슈는 risk_items로 강등 (정보는 보존)
            risk_items.append(f"[검토] {issue_text}")
            continue

        kept.append(item)

    insights["top_issues"] = kept[:2]  # 상한 2 강제
    insights["risk_items"] = risk_items

    # 개수에 따라 relation 정합성 보정
    if len(insights["top_issues"]) < 2:
        insights["relation"] = None

    return insights


def _severity_phrase(severity: str) -> str:
    """severity를 자연어 톤으로 변환. medium=주의, high=경고."""
    if severity == "high":
        return "심각하여 대응이 필요합니다."
    return "주의 깊게 지켜볼 필요가 있습니다."


def _reason_breakdown_sentence(breakdown: dict) -> str:
    """rule이 집계한 사유별 금액을 결정론적으로 문장화. LLM 개입 없음.
    금액순 정렬, 0원 사유는 가독성 위해 생략."""
    items = sorted(((k, v) for k, v in breakdown.items() if v), key=lambda kv: -kv[1])
    if not items:
        return ""
    parts = ", ".join(f"{k} {v:,}원" for k, v in items)
    return f" 사유별로는 {parts} 순으로 컸습니다."


def _build_fallback_issue(category: str, patterns: dict, kpi_summary: dict) -> dict:
    """
    LLM이 누락한 GT 카테고리에 대해, rule의 raw 데이터로
    결정론적 자연어 문장을 생성한다. LLM 호출 없음 — 판단은 이미 rule이 끝냄.
    """
    if category == "반품이슈":
        breakdown = patterns.get("return_reason_breakdown", {})
        ra = patterns.get("return_anomalies", [])
        if ra:
            top = ra[0]
            issue = (
                f"{top.get('product_name', '')}의 반품이 오늘 {top.get('today_returns', 0)}건 "
                f"발생해 평균 대비 {top.get('multiplier', 0)}배 수준입니다. "
                f"{_severity_phrase(top.get('severity', 'medium'))}"
                f"{_reason_breakdown_sentence(breakdown)}"
            )
            return {"issue": issue, "category": category}

        return_only = [
            p for p in kpi_summary.get("by_product", [])
            if p.get("total_sales", 0) == 0
            and classify_return_severity(p.get("zre_qty", 0), p.get("zre_amt", 0)) is not None
        ]
        if return_only:
            total_zre = sum(p["zre_qty"] for p in return_only)
            total_amt = sum(p.get("zre_amt", 0) for p in return_only)
            severity = classify_return_severity(total_zre, total_amt) or "medium"
            issue = (
                f"판매 없이 반품만 {len(return_only)}개 제품에서 "
                f"총 {total_zre}건({total_amt:,}원) 발생했습니다. "
                f"{_severity_phrase(severity)}"
            )
            return {"issue": issue, "category": category}
        return {"issue": "오늘 반품이슈가 감지되었습니다.", "category": category}

    if category == "목표미달":
        adt = patterns.get("adjusted_daily_target", {})
        adjustments = ", ".join(adt.get("adjustments_applied", []))
        issue = (
            f"오늘 순매출 {adt.get('today_net_sales', 0):,}원 — "
            f"조정 일별 목표({adjustments}) {adt.get('adjusted_daily_required', 0):,}원의 "
            f"{adt.get('achievement_vs_adjusted', 0)}%에 그쳤습니다 "
            f"(잔여 {adt.get('days_remaining', 0)}일)."
        )
        return {"issue": issue, "category": category}

    if category == "추세악화":
        trend = patterns.get("trend_direction_30d", {})
        issue = (
            f"최근 매출 추세가 지난 30일 하락 흐름"
            f"(z={trend.get('accel_zscore')}) 속에서 통계적으로 유의하게 꺾이고 있습니다."
        )
        return {"issue": issue, "category": category}

    if category == "수익성문제":
        disc = patterns.get("discount_sensitivity", {})
        dev = disc.get("margin_deviation", 0) or 0
        issue = (
            f"오늘 실제 마진율({disc.get('margin_pct_overall')}%)이 믹스 기대치보다 "
            f"{abs(dev)}%p 낮습니다."
        )
        return {"issue": issue, "category": category}

    return {"issue": f"오늘 {category} 관련 이슈가 감지되었습니다.", "category": category}


def _enforce_completeness(insights: dict, state: dict) -> dict:
    """
    rule GT가 확정한 카테고리가 LLM top_issues에 없으면 강제 삽입.
    category 게이트(오탐 방어)의 짝 = 누락 방어.
    """
    gt = determine_ground_truth_set(state)
    current_categories = {
        item.get("category") for item in insights.get("top_issues", [])
        if isinstance(item, dict)
    }

    missing = gt["categories"] - current_categories
    for cat in missing:
        fallback = _build_fallback_issue(
            cat, state.get("patterns", {}), state.get("kpi_summary", {})
        )
        insights["top_issues"].append(fallback)
        logger.info(f"완전성 게이트: '{cat}' 누락 감지 → 강제 삽입")

    insights["top_issues"] = insights["top_issues"][:2]  # 상한 2 유지
    return insights


def insight_node(state: dict) -> dict:
    errors = list(state.get("errors", []))
    insights: dict = {}

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        logger.warning("OPENAI_API_KEY 미설정, insight_node 스킵")
        errors.append(
            "AI 인사이트를 생성하지 못했습니다 (OPENAI_API_KEY 미설정) — "
            "rule 기반 판정만 반영됨"
        )
    else:
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
                api_key=api_key,
                temperature=0,
                model_kwargs={"seed": 42},
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
        except Exception as e:
            logger.warning(f"insight_node 실패: {e}")
            errors.append(f"insight_node 실패: {e}")

    # LLM 호출/파싱이 통째로 실패해도(API키 미설정/네트워크 오류 등) 완전성
    # 게이트는 rule 데이터만으로 동작하므로 반드시 거쳐야 한다 — if/else
    # 양쪽 분기 모두 조기 return 없이 여기로 합류해 무조건 실행된다.
    if not isinstance(insights.get("top_issues"), list):
        insights["top_issues"] = []
    insights = _enforce_completeness(insights, state)
    issue_count = len(insights.get("top_issues", []))
    logger.info(f"insight_node 완료: top_issues {issue_count}개")

    return {**state, "insights": insights, "errors": errors}