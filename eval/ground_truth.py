"""
eval/ground_truth.py
날짜별로 "그날 가장 중요했던 이슈가 무엇이었어야 하는가"를
rule-based로 자동 판정한다.

주의: 이 ground truth는 pattern_nodes.py와 동일한 임계값을 사용하므로
insight_node 평가 시 순환논리 위험이 있다. 이 함수는 1차 스크리닝용으로만
쓰고, 최종 신뢰도 판단에는 사람이 직접 라벨링한 anchor set(별도 작업)을
반드시 함께 참조해야 한다.
"""
import logging

logger = logging.getLogger(__name__)


def determine_ground_truth(state: dict) -> dict:
    """
    state(kpi_compute_node, pattern_detect_node까지 실행된 상태)를 받아
    그날의 정답 이슈 카테고리와 근거를 반환한다.

    반환 형식:
    {
        "category": "반품이슈" | "목표미달" | "수익성문제" | "정상",
        "reason": "판정 근거 문장",
        "severity": "high" | "medium" | "low" | "none"
    }

    우선순위: 반품이슈 > 목표미달 > 수익성문제 > 정상
    (여러 개 해당 시 가장 심각한 것 하나만 반환)
    """
    patterns = state.get("patterns", {})
    target_summary = state.get("target_summary", {})

    candidates = []

    # 1. 반품 이슈 — return_anomalies에 있거나, ZRE 전용 제품이 있는 경우
    return_anomalies = patterns.get("return_anomalies", [])
    if return_anomalies:
        max_multiplier = max(r.get("multiplier", 0) for r in return_anomalies)
        candidates.append({
            "category": "반품이슈",
            "reason": (
                f"{len(return_anomalies)}개 제품에서 반품률 이상 감지, "
                f"최대 평균의 {max_multiplier}배"
            ),
            "severity": "high" if max_multiplier >= 5 else "medium",
            "priority": 1,
        })

    kpi_summary = state.get("kpi_summary", {})
    by_product = kpi_summary.get("by_product", [])
    return_only = [p for p in by_product
                   if p.get("total_sales") == 0 and p.get("zre_qty", 0) > 0]
    if return_only:
        total_zre = sum(p["zre_qty"] for p in return_only)
        candidates.append({
            "category": "반품이슈",
            "reason": (
                f"오늘 신규 판매 없이 반품만 발생한 제품 {len(return_only)}개, "
                f"총 {total_zre}건"
            ),
            "severity": "high" if total_zre >= 50 else "medium",
            "priority": 1,
        })

    # 2. 목표 미달 — 전체 또는 플랫폼 달성률 기준
    total_achievement = target_summary.get("total_achievement_pct", 100)
    if total_achievement < 50:
        candidates.append({
            "category": "목표미달",
            "reason": f"전체 목표 달성률 {total_achievement}%로 50% 미만",
            "severity": "high",
            "priority": 2,
        })
    elif total_achievement < 70:
        candidates.append({
            "category": "목표미달",
            "reason": f"전체 목표 달성률 {total_achievement}%로 70% 미만",
            "severity": "medium",
            "priority": 2,
        })

    # 3. 수익성 문제 — 마진율 기준
    discount = patterns.get("discount_sensitivity", {})
    margin_pct = discount.get("margin_pct_overall")
    if margin_pct is not None and margin_pct < 25:
        candidates.append({
            "category": "수익성문제",
            "reason": f"오늘 전체 마진율 {margin_pct}%로 25% 미만",
            "severity": "high",
            "priority": 3,
        })
    elif margin_pct is not None and margin_pct < 30:
        candidates.append({
            "category": "수익성문제",
            "reason": f"오늘 전체 마진율 {margin_pct}%로 30% 미만",
            "severity": "medium",
            "priority": 3,
        })

    # 편중: 다른 이슈가 없을 때만, 최하위 우선순위
    movers = patterns.get("category_movers", [])
    if movers:
        dominant = [
            m for m in movers
            if m.get("flag") and m.get("share_pct", 0) > 80
        ]
        if dominant:
            candidates.append({
                "category": "편중",
                "reason": (
                    f"{dominant[0]['category_l1']} 매출 비중 "
                    f"{dominant[0]['share_pct']}% — 구조적 집중"
                ),
                "severity": "low",
                "priority": 99,
            })

    if not candidates:
        return {
            "category": "정상",
            "reason": "주요 임계값을 벗어난 이슈 없음",
            "severity": "none",
        }

    # severity 우선, 그 다음 priority(낮을수록 우선) 기준 정렬
    severity_rank = {"high": 0, "medium": 1, "low": 2}
    candidates.sort(key=lambda x: (severity_rank.get(x["severity"], 9), x["priority"]))

    top = candidates[0]
    return {
        "category": top["category"],
        "reason": top["reason"],
        "severity": top["severity"],
    }
