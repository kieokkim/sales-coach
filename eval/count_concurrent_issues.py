"""
eval/count_concurrent_issues.py
91일 전체에서 동시에 발생하는 유의미 이슈(medium 이상) 개수 분포를 조사한다.
top_issues 복수화 시 상한을 데이터 기반으로 정하기 위한 조사 스크립트.

편중(구조적 특성)은 제외 — "오늘 주목할 이슈"가 아니므로.

실행: uv run python eval/count_concurrent_issues.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime, timedelta
from collections import Counter

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

from nodes.preprocess_nodes import _preprocess_offline, _preprocess_online
from nodes.kpi_nodes import kpi_compute_node
from nodes.db_nodes import db_load_cumulative_node
from nodes.target_nodes import target_compare_node
from nodes.anomaly_nodes import anomaly_detect_node
from nodes.pattern_nodes import pattern_detect_node

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def count_issues_for_date(offline_raw, online_raw, date_str):
    """
    해당 날짜의 patterns를 계산하고, ground_truth와 동일한 기준으로
    medium 이상 severity 카테고리가 몇 개인지 센다. 편중은 제외.
    """
    off_f = _preprocess_offline(offline_raw.copy(), date_str)
    on_f = _preprocess_online(online_raw.copy(), date_str)

    if off_f.empty and on_f.empty:
        return None

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

    try:
        state = kpi_compute_node(state)
        state = db_load_cumulative_node(state)
        state = target_compare_node(state)
        state = anomaly_detect_node(state)
        state = pattern_detect_node(state)
    except Exception as e:
        logger.warning(f"{date_str} 파이프라인 실패: {e}")
        return None

    patterns = state.get("patterns", {})
    categories = []  # (category, severity) — medium 이상만

    # 1. 반품이슈
    return_anomalies = patterns.get("return_anomalies", [])
    if return_anomalies:
        max_mult = max(r.get("multiplier", 0) for r in return_anomalies)
        sev = "high" if max_mult >= 5 else "medium"
        categories.append(("반품이슈", sev))

    kpi_summary = state.get("kpi_summary", {})
    by_product = kpi_summary.get("by_product", [])
    return_only = [p for p in by_product
                   if p.get("total_sales") == 0 and p.get("zre_qty", 0) > 0]
    if return_only:
        total_zre = sum(p["zre_qty"] for p in return_only)
        sev = "high" if total_zre >= 50 else "medium"
        # 이미 반품이슈 있으면 중복 카운트 안 함
        if not any(c[0] == "반품이슈" for c in categories):
            categories.append(("반품이슈", sev))

    # 2. 수익성문제 (믹스 편차 기준)
    discount = patterns.get("discount_sensitivity", {})
    dev = discount.get("margin_deviation")
    if dev is not None:
        if dev <= -5:
            categories.append(("수익성문제", "high"))
        elif dev <= -3:
            categories.append(("수익성문제", "medium"))

    # 3. 목표미달 (조정 일별 목표 severity)
    adt = patterns.get("adjusted_daily_target", {})
    if adt.get("severity") in ("high", "medium"):
        categories.append(("목표미달", adt["severity"]))

    # 4. 추세악화 (가속하락)
    trend = patterns.get("trend_direction_30d", {})
    if trend.get("acceleration") == "가속하락":
        categories.append(("추세악화", "medium"))

    return {
        "date": date_str,
        "count": len(categories),
        "categories": categories,
    }


def main():
    offline_raw = pd.read_excel(os.path.join(DATA_DIR, "sample_offline_3months.xlsx"))
    online_raw = pd.read_excel(os.path.join(DATA_DIR, "sample_online_3months.xlsx"))

    start = datetime(2025, 4, 1)
    end = datetime(2025, 6, 30)
    results = []

    d = start
    while d <= end:
        r = count_issues_for_date(offline_raw, online_raw, d.strftime("%Y%m%d"))
        if r:
            results.append(r)
        d += timedelta(days=1)

    # 분포 집계
    count_dist = Counter(r["count"] for r in results)
    total = len(results)

    print(f"\n{'='*55}")
    print(f"동시 발생 이슈 개수 분포 (편중 제외, medium 이상)")
    print(f"전체 {total}일")
    print(f"{'='*55}")
    for n in sorted(count_dist.keys()):
        days = count_dist[n]
        pct = round(days / total * 100, 1)
        bar = "█" * int(pct / 2)
        print(f"  {n}개 이슈: {days:2d}일 ({pct:4.1f}%) {bar}")

    # 2개 이상인 날의 카테고리 조합 상세
    multi = [r for r in results if r["count"] >= 2]
    print(f"\n{'='*55}")
    print(f"2개 이상 동시 발생: {len(multi)}일")
    print(f"{'='*55}")
    combo_counter = Counter()
    for r in multi:
        combo = " + ".join(sorted(c[0] for c in r["categories"]))
        combo_counter[combo] += 1
    for combo, cnt in combo_counter.most_common():
        print(f"  {combo}: {cnt}일")

    # 3개 이상인 날 상세 (상한 결정 핵심)
    triple = [r for r in results if r["count"] >= 3]
    print(f"\n{'='*55}")
    print(f"3개 이상 동시 발생: {len(triple)}일")
    print(f"{'='*55}")
    if triple:
        for r in triple:
            cats = ", ".join(f"{c[0]}({c[1]})" for c in r["categories"])
            print(f"  {r['date']}: {cats}")
    else:
        print("  없음 — 상한 2로 충분")


if __name__ == "__main__":
    main()
