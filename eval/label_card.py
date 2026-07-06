"""
eval/label_card.py
anchor_set 라벨링용 — 특정 날짜들의 판단 지표를 카드 형식으로 출력.
사람이 top_issues 정답을 직접 판단하기 위한 재료.

판단(정답 category)은 내리지 않는다. 사실 + 문턱 주석만 병기.

실행: uv run python eval/label_card.py 20250501 20250516 20250518 20250525 20250526 20250531
"""
import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

from nodes.preprocess_nodes import _preprocess_offline, _preprocess_online
from nodes.kpi_nodes import kpi_compute_node
from nodes.db_nodes import db_load_cumulative_node
from nodes.target_nodes import target_compare_node
from nodes.anomaly_nodes import anomaly_detect_node
from nodes.pattern_nodes import pattern_detect_node
from nodes.insight_node import insight_node
from eval.ground_truth import determine_ground_truth_set

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
OFFLINE_FILE = os.path.join(DATA_DIR, "sample_offline_3months.xlsx")
ONLINE_FILE = os.path.join(DATA_DIR, "sample_online_3months.xlsx")


def _fmt(v):
    """None 안전 포맷."""
    return v if v is not None else "N/A"


def card(date_str: str, offline_raw: pd.DataFrame, online_raw: pd.DataFrame):
    off_f = _preprocess_offline(offline_raw.copy(), date_str)
    on_f = _preprocess_online(online_raw.copy(), date_str)

    state = {
        "offline_processed": off_f,
        "online_processed": on_f,
        "report_date": date_str,
        "errors": [],
        "kpi_cumulative": {},
        "target_summary": {},
        "anomalies": [],
        "patterns": {},
    }

    state = kpi_compute_node(state)
    state = db_load_cumulative_node(state)
    state = target_compare_node(state)
    state = anomaly_detect_node(state)
    state = pattern_detect_node(state)

    patterns = state.get("patterns", {})
    kpi_total = state.get("kpi_total", {})
    gt = determine_ground_truth_set(state)

    print(f"\n{'='*56}")
    print(f"  {date_str}")
    print(f"{'='*56}")

    # 매출
    print(f"  [매출] 총매출 {kpi_total.get('total_sales', 0):,}원 / "
          f"순매출(반품차감) {kpi_total.get('net_sales', 0):,}원")

    # 목표
    adt = patterns.get("adjusted_daily_target", {})
    print(f"\n  [목표] severity={_fmt(adt.get('severity'))} / "
          f"달성률={_fmt(adt.get('achievement_vs_adjusted'))}% / "
          f"잔여{_fmt(adt.get('days_remaining'))}일")
    print(f"         조정목표 {adt.get('adjusted_daily_required', 0):,}원 / "
          f"오늘순매출 {adt.get('today_net_sales', 0):,}원")
    print(f"         (문턱: 잔여≥7일이면 달성률80%미만, <7일이면 60%미만=목표미달")
    print(f"          severity: 잔여<7일=high / <14일=medium / 그외=low)")

    # 반품
    ra = patterns.get("return_anomalies", [])
    kpi_summary = state.get("kpi_summary", {})
    return_only = [p for p in kpi_summary.get("by_product", [])
                   if p.get("total_sales") == 0 and p.get("zre_qty", 0) > 0]
    max_mult = max((r.get("multiplier", 0) for r in ra), default=0)
    print(f"\n  [반품] 비율이상 {len(ra)}건" +
          (f" (최대 {max_mult}배)" if ra else "") +
          f" / 판매없이반품만 {len(return_only)}개 제품")
    if return_only:
        tot = sum(p["zre_qty"] for p in return_only)
        print(f"         반품전용 총 {tot}건")
    print(f"         (문턱: multiplier≥3=이상감지 / GT는 ≥5배 또는 반품전용≥50건=high, 그외 medium)")

    # 마진
    disc = patterns.get("discount_sensitivity", {})
    print(f"\n  [마진] 실제 {_fmt(disc.get('margin_pct_overall'))}% / "
          f"믹스기대 {_fmt(disc.get('theoretical_margin_pct'))}% / "
          f"편차 {_fmt(disc.get('margin_deviation'))}%p")
    print(f"         (문턱: 편차 -3%p이하=수익성문제 medium / -5%p이하=high)")

    # 추세
    tr = patterns.get("trend_direction_30d", {})
    print(f"\n  [추세] 30일방향={_fmt(tr.get('overall_direction'))}"
          f"({_fmt(tr.get('overall_change_pct'))}%) / "
          f"가속={_fmt(tr.get('acceleration'))}"
          f"({_fmt(tr.get('acceleration_pct'))}%)")
    print(f"         (문턱: 가속 -15%이하=가속하락=추세악화 / -5~-15%=하락중(추세악화 아님))")

    # 프로모션
    promo = patterns.get("promo_effect", {})
    if promo.get("active"):
        print(f"\n  [프로모션] active=True / 리프트 {_fmt(promo.get('sales_lift_pct'))}%")
    else:
        print(f"\n  [프로모션] active=False")

    # 편중
    movers = patterns.get("category_movers", [])
    if movers:
        top_mover = movers[0]
        print(f"\n  [편중] {top_mover.get('category_l1')} "
              f"{top_mover.get('share_pct')}% (flag={top_mover.get('flag')})")
        print(f"         (편중은 구조적 특성 → top_issues 집합에서 제외)")

    # 판정 비교 (LLM 호출)
    state = insight_node(state)
    llm_issues = state.get("insights", {}).get("top_issues", [])
    llm_cats = set(it.get("category") for it in llm_issues
                   if isinstance(it, dict) and it.get("category"))

    print(f"\n  ── 판정 비교 ──")
    print(f"  rule GT 집합 : {gt['categories'] or '∅(정상)'}")
    print(f"  LLM 예측 집합: {llm_cats or '∅(정상)'}")
    print(f"  LLM 서술:")
    for it in llm_issues:
        if isinstance(it, dict):
            print(f"    - [{it.get('category')}] {str(it.get('issue', ''))[:60]}")


def main():
    if len(sys.argv) < 2:
        logger.error("날짜 인자 필요. 예: uv run python eval/label_card.py 20250501")
        sys.exit(1)

    offline_raw = pd.read_excel(OFFLINE_FILE)
    online_raw = pd.read_excel(ONLINE_FILE)
    for ds in sys.argv[1:]:
        card(ds, offline_raw, online_raw)


if __name__ == "__main__":
    main()
