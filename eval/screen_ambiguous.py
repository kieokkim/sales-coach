"""
eval/screen_ambiguous.py
91일 전체를 순회하며 ground_truth 판정 시
수익성문제/목표미달이 동시에 candidate로 발생하는 날짜를 추출한다.
anchor_set 라벨링 우선순위 결정용.

실행: uv run python eval/screen_ambiguous.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime, timedelta

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
OFFLINE_FILE = os.path.join(DATA_DIR, "sample_offline_3months.xlsx")
ONLINE_FILE = os.path.join(DATA_DIR, "sample_online_3months.xlsx")


def main():
    offline_raw = pd.read_excel(OFFLINE_FILE)
    online_raw = pd.read_excel(ONLINE_FILE)

    start = datetime(2025, 4, 1)
    end = datetime(2025, 6, 30)
    ambiguous_dates = []

    d = start
    while d <= end:
        date_str = d.strftime("%Y%m%d")
        off_f = _preprocess_offline(offline_raw.copy(), date_str)
        on_f = _preprocess_online(online_raw.copy(), date_str)

        if not off_f.empty or not on_f.empty:
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

                patterns = state.get("patterns", {})
                discount = patterns.get("discount_sensitivity", {})
                adt = patterns.get("adjusted_daily_target", {})

                margin = discount.get("margin_pct_overall")
                has_margin_issue = margin is not None and margin < 30
                has_target_issue = adt.get("severity") in ("high", "medium")

                if has_margin_issue and has_target_issue:
                    ambiguous_dates.append({
                        "date": date_str,
                        "margin_pct": margin,
                        "target_severity": adt.get("severity"),
                        "achievement_vs_adjusted": adt.get("achievement_vs_adjusted"),
                        "days_remaining": adt.get("days_remaining"),
                    })
            except Exception as e:
                logger.warning(f"{date_str} 스크리닝 실패: {e}")

        d += timedelta(days=1)

    print(f"모호 케이스 {len(ambiguous_dates)}개 발견:\n")
    for item in ambiguous_dates:
        print(
            f"  {item['date']}: 마진율={item['margin_pct']}%, "
            f"목표심각도={item['target_severity']}, "
            f"달성률={item['achievement_vs_adjusted']}%, "
            f"잔여일={item['days_remaining']}"
        )


if __name__ == "__main__":
    main()
