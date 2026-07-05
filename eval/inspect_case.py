"""
eval/inspect_case.py
특정 날짜의 patterns 전체를 사람이 읽기 좋은 형태로 출력한다.
anchor_set 라벨링 판단 및 스키마 재검토용.

실행: uv run python eval/inspect_case.py 20250520
"""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

from nodes.preprocess_nodes import _preprocess_offline, _preprocess_online
from nodes.kpi_nodes import kpi_compute_node
from nodes.db_nodes import db_load_cumulative_node
from nodes.target_nodes import target_compare_node
from nodes.anomaly_nodes import anomaly_detect_node
from nodes.pattern_nodes import pattern_detect_node
from eval.ground_truth import determine_ground_truth

logging.basicConfig(level=logging.WARNING)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
OFFLINE_FILE = os.path.join(DATA_DIR, "sample_offline_3months.xlsx")
ONLINE_FILE = os.path.join(DATA_DIR, "sample_online_3months.xlsx")


def inspect(date_str: str):
    offline_raw = pd.read_excel(OFFLINE_FILE)
    online_raw = pd.read_excel(ONLINE_FILE)

    off_f = _preprocess_offline(offline_raw, date_str)
    on_f = _preprocess_online(online_raw, date_str)

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
    gt = determine_ground_truth(state)

    print(f"=== {date_str} ===")
    print(f"[Rule 판정] {gt['category']} ({gt['severity']})")
    print(f"근거: {gt['reason']}")

    discount = patterns.get("discount_sensitivity", {})
    print(f"\n[마진/할인]")
    print(f"  전체 마진율: {discount.get('margin_pct_overall')}%")
    print(f"  총 마진: {discount.get('total_margin', 0):,}원")
    print(f"  할인 버킷: {json.dumps(discount.get('bucket_summary', {}), ensure_ascii=False)}")

    adt = patterns.get("adjusted_daily_target", {})
    print(f"\n[목표 달성]")
    print(f"  오늘 순매출: {adt.get('today_net_sales', 0):,}원")
    print(f"  조정 일별 목표: {adt.get('adjusted_daily_required', 0):,}원")
    print(f"  달성률: {adt.get('achievement_vs_adjusted')}%")
    print(f"  잔여일: {adt.get('days_remaining')}일")
    print(f"  적용 보정: {adt.get('adjustments_applied', [])}")
    print(f"  심각도: {adt.get('severity')}")

    trend = patterns.get("trend_direction_30d", {})
    print(f"\n[30일 추세]")
    print(f"  방향: {trend.get('overall_direction')} ({trend.get('overall_change_pct')}%)")
    print(f"  가속도: {trend.get('acceleration')} ({trend.get('acceleration_pct')}%)")

    returns = patterns.get("return_anomalies", [])
    print(f"\n[반품 이상] {len(returns)}건")

    movers = patterns.get("category_movers", [])
    print(f"\n[카테고리 비중]")
    for m in movers[:3]:
        print(f"  {m['category_l1']}: {m['share_pct']}%")

    promo = patterns.get("promo_effect", {})
    print(f"\n[프로모션] active={promo.get('active', False)}")


if __name__ == "__main__":
    inspect(sys.argv[1])
