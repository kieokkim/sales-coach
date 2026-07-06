"""
eval/ground_truth.py
날짜별로 "그날 가장 중요했던 이슈가 무엇이었어야 하는가"를
rule-based로 자동 판정한다.

주의: 이 ground truth는 pattern_nodes.py와 동일한 임계값을 사용하므로
insight_node 평가 시 순환논리 위험이 있다. 이 함수는 1차 스크리닝용으로만
쓰고, 최종 신뢰도 판단에는 사람이 직접 라벨링한 anchor set(별도 작업)을
반드시 함께 참조해야 한다.
"""
import json
import logging
import os

logger = logging.getLogger(__name__)


def _load_anchor_set() -> dict:
    """사람이 라벨링한 anchor set을 로드한다."""
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "anchor_set.json"
    )
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {k: v for k, v in data.items() if not k.startswith("_")}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _return_severity(return_anomalies: list) -> str:
    """
    반품이슈 severity를 통계적 격차로 판정한다 (매직넘버 없음).
    high: 오늘 반품률 신뢰구간 하한이 평소 상한의 2배 이상 (큰 격차)
    medium: 유의하나 격차가 그보다 작음
    (anomaly는 today_lower > hist_upper일 때만 생성되므로 최소 medium)
    """
    for a in return_anomalies:
        lower = a.get("today_lower_bound", 0)
        upper = a.get("hist_upper_bound", 0)
        if upper > 0 and lower >= upper * 2:
            return "high"
    return "medium"


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
    report_date = state.get("report_date", "")
    if len(report_date) == 8:
        date_key = f"{report_date[:4]}-{report_date[4:6]}-{report_date[6:8]}"
    else:
        date_key = report_date

    anchor_set = _load_anchor_set()
    if date_key in anchor_set:
        entry = anchor_set[date_key]
        return {
            "category": entry.get("top_issue_category", "정상"),
            "reason": entry.get("note", "사람이 직접 라벨링한 케이스"),
            "severity": entry.get("severity", "none"),
            "source": "anchor_set",
        }

    patterns = state.get("patterns", {})
    kpi_total = state.get("kpi_total", {})

    candidates = []

    # 1. 반품 이상 (1순위) — Wilson 통계 격차 기반 severity
    return_anomalies = patterns.get("return_anomalies", [])
    if return_anomalies:
        max_multiplier = max(r.get("multiplier", 0) for r in return_anomalies)
        candidates.append({
            "category": "반품이슈",
            "reason": (
                f"{len(return_anomalies)}개 제품 반품률 통계적 유의 상승 "
                f"(신뢰구간 비중첩), 최대 평균의 {max_multiplier}배"
            ),
            "severity": _return_severity(return_anomalies),
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
                f"판매 없이 반품만 {len(return_only)}개 제품 "
                f"총 {total_zre}건 발생"
            ),
            "severity": "high" if total_zre >= 50 else "medium",
            "priority": 1,
        })

    # 2. 수익성 문제 (2순위) — 오늘 믹스 이론 마진 대비 실제 마진 이탈폭
    discount = patterns.get("discount_sensitivity", {})
    margin_deviation = discount.get("margin_deviation")
    if margin_deviation is not None:
        if margin_deviation <= -5:
            candidates.append({
                "category": "수익성문제",
                "reason": (
                    f"실제 마진이 오늘 믹스 기대치보다 {abs(margin_deviation)}%p 낮음 "
                    f"(실제 {discount.get('margin_pct_overall')}% vs "
                    f"기대 {discount.get('theoretical_margin_pct')}%) — 할인/가격 이슈"
                ),
                "severity": "high",
                "priority": 2,
            })
        elif margin_deviation <= -3:
            candidates.append({
                "category": "수익성문제",
                "reason": (
                    f"실제 마진이 기대치보다 {abs(margin_deviation)}%p 낮음 "
                    f"(할인 영향 추정)"
                ),
                "severity": "medium",
                "priority": 2,
            })

    # 3. 목표 미달 (3순위) — 조정 일별 목표 기준 + 순매출
    adt = patterns.get("adjusted_daily_target", {})
    if adt and adt.get("severity") in ("high", "medium", "low"):
        adj_req = adt.get("adjusted_daily_required", 0)
        net_sales = adt.get("today_net_sales", 0)
        achievement = adt.get("achievement_vs_adjusted", 0)
        days_remaining = adt.get("days_remaining", 30)
        adjustments = ", ".join(adt.get("adjustments_applied", []))

        candidates.append({
            "category": "목표미달",
            "reason": (
                f"오늘 순매출 {net_sales:,}원 — "
                f"조정 일별 목표({adjustments}) {adj_req:,}원의 "
                f"{achievement}% (잔여 {days_remaining}일)"
            ),
            "severity": adt["severity"],
            "priority": 3,
        })

    # 4. 추세 가속 하락 (4순위)
    trend_30d = patterns.get("trend_direction_30d", {})
    acceleration = trend_30d.get("acceleration", "")
    if acceleration == "가속하락":
        change = trend_30d.get("overall_change_pct", 0)
        acc_pct = trend_30d.get("acceleration_pct", 0)
        candidates.append({
            "category": "추세악화",
            "reason": (
                f"30일 방향 {change:+.1f}%, "
                f"최근 7일 가속 {acc_pct:+.1f}% — 하락 가속 중"
            ),
            "severity": "medium",
            "priority": 4,
        })

    # 5. 편중 (최하위, 다른 이슈 없을 때만)
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
                    f"{dominant[0]['share_pct']}%"
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


def determine_ground_truth_set(state: dict) -> dict:
    """
    그날 유효한 이슈 카테고리들의 집합을 반환한다 (Eval용).
    determine_ground_truth가 최상위 1개를 반환하는 것과 달리,
    medium 이상 severity 카테고리를 모두 담는다.
    top_issues 복수화(상한 2)에 대응하는 채점 기준.

    편중은 구조적 특성이므로 집합에서 제외 (top_issues 대상 아님).
    anchor_set에 라벨링된 날짜면 그것을 우선한다.

    반환:
    {
        "categories": set[str],   # 예: {"목표미달", "반품이슈"}
        "source": "anchor_set" | "rule",
        "detail": [{"category": str, "severity": str}, ...],
    }
    """
    report_date = state.get("report_date", "")
    if len(report_date) == 8:
        date_key = f"{report_date[:4]}-{report_date[4:6]}-{report_date[6:8]}"
    else:
        date_key = report_date

    anchor_set = _load_anchor_set()
    if date_key in anchor_set:
        entry = anchor_set[date_key]
        cat = entry.get("top_issue_category", "정상")
        cat_set = {cat} if cat not in ("정상", "편중") else set()
        return {
            "categories": cat_set,
            "source": "anchor_set",
            "detail": [{"category": cat, "severity": entry.get("severity", "none")}],
        }

    # rule 기반 — determine_ground_truth의 candidate 로직과 동일 기준
    patterns = state.get("patterns", {})
    detail = []

    # 반품이슈 — Wilson 통계 격차 기반 severity
    return_anomalies = patterns.get("return_anomalies", [])
    if return_anomalies:
        detail.append({"category": "반품이슈",
                       "severity": _return_severity(return_anomalies)})
    else:
        kpi_summary = state.get("kpi_summary", {})
        return_only = [p for p in kpi_summary.get("by_product", [])
                       if p.get("total_sales") == 0 and p.get("zre_qty", 0) > 0]
        if return_only:
            total_zre = sum(p["zre_qty"] for p in return_only)
            detail.append({"category": "반품이슈",
                           "severity": "high" if total_zre >= 50 else "medium"})

    # 수익성문제 (믹스 상대편차)
    discount = patterns.get("discount_sensitivity", {})
    dev = discount.get("margin_deviation")
    if dev is not None:
        if dev <= -5:
            detail.append({"category": "수익성문제", "severity": "high"})
        elif dev <= -3:
            detail.append({"category": "수익성문제", "severity": "medium"})

    # 목표미달 (low 포함 — 실제 미달인 날을 미달로 인정, 측정 교정)
    adt = patterns.get("adjusted_daily_target", {})
    if adt.get("severity") in ("high", "medium", "low"):
        detail.append({"category": "목표미달", "severity": adt["severity"]})

    # 추세악화
    trend = patterns.get("trend_direction_30d", {})
    if trend.get("acceleration") == "가속하락":
        detail.append({"category": "추세악화", "severity": "medium"})

    cat_set = set(d["category"] for d in detail)
    return {
        "categories": cat_set,
        "source": "rule",
        "detail": detail,
    }
