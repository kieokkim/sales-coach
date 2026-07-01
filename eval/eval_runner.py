"""
eval/eval_runner.py
샘플 데이터 기간(2025-04-01 ~ 2025-06-30) 전체를 순회하며
Eval 1(insight 정확도) + Eval 2(action 품질)를 자동 측정하고
종합 리포트를 출력한다.

실행: uv run python eval/eval_runner.py
실행: uv run python eval/eval_runner.py --start 20250501 --end 20250531
"""
import argparse
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
from nodes.insight_node import insight_node
from nodes.action_node import action_node

from eval.ground_truth import determine_ground_truth
from eval.eval_insight import evaluate_insight
from eval.eval_action import evaluate_actions

logging.basicConfig(level=logging.WARNING)  # eval 중 노이즈 로그 억제
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
OFFLINE_FILE = os.path.join(DATA_DIR, "sample_offline_3months.xlsx")
ONLINE_FILE = os.path.join(DATA_DIR, "sample_online_3months.xlsx")


def run_single_date(offline_raw, online_raw, date_str: str) -> dict:
    """단일 날짜에 대해 파이프라인을 실행하고 Eval 1+2를 측정한다."""
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
        "insights": {},
        "actions": [],
    }

    try:
        state = kpi_compute_node(state)
        state = db_load_cumulative_node(state)
        state = target_compare_node(state)
        state = anomaly_detect_node(state)
        state = pattern_detect_node(state)
        state = insight_node(state)
        state = action_node(state)
    except Exception as e:
        logger.warning(f"{date_str} 파이프라인 실행 실패: {e}")
        return None

    gt = determine_ground_truth(state)
    eval1 = evaluate_insight(state, gt)
    eval2 = evaluate_actions(state)

    return {
        "date": date_str,
        "ground_truth": gt,
        "eval1_match": eval1["match"],
        "eval1_detail": eval1,
        "eval2_avg_score": eval2["avg_score"],
        "eval2_detail": eval2,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="20250401")
    parser.add_argument("--end", default="20250630")
    args = parser.parse_args()

    print(f"Eval 실행: {args.start} ~ {args.end}")
    print("파일 로드 중...")

    offline_raw = pd.read_excel(OFFLINE_FILE)
    online_raw = pd.read_excel(ONLINE_FILE)

    start_dt = datetime.strptime(args.start, "%Y%m%d")
    end_dt = datetime.strptime(args.end, "%Y%m%d")
    date_list = []
    d = start_dt
    while d <= end_dt:
        date_list.append(d.strftime("%Y%m%d"))
        d += timedelta(days=1)

    results = []
    for i, date_str in enumerate(date_list):
        result = run_single_date(offline_raw, online_raw, date_str)
        if result:
            results.append(result)
        if (i + 1) % 10 == 0:
            print(f"  진행중: {date_str} ({i+1}/{len(date_list)})")

    if not results:
        print("평가 가능한 데이터가 없습니다.")
        return

    # 집계
    total = len(results)
    eval1_pass = sum(1 for r in results if r["eval1_match"])
    eval1_accuracy = round(eval1_pass / total * 100, 1)

    eval2_scores = [r["eval2_avg_score"] for r in results]
    eval2_avg = round(sum(eval2_scores) / len(eval2_scores), 2)

    eval3_composite = round(eval1_accuracy / 100 * (eval2_avg / 4) * 100, 1)

    print("\n" + "=" * 50)
    print(f"전체 케이스: {total}개")
    print(f"\n[Eval 1] Insight 정확도: {eval1_accuracy}% ({eval1_pass}/{total})")
    print(f"[Eval 2] Action 품질 평균: {eval2_avg} / 4.0")
    print(f"[Eval 3] 종합 점수: {eval3_composite}%")
    print("=" * 50)

    # 실패 케이스 상세 출력 (최대 10개)
    failures = [r for r in results if not r["eval1_match"]]
    if failures:
        print(f"\nEval 1 FAIL 케이스 ({len(failures)}개, 최대 10개 표시):")
        for r in failures[:10]:
            print(
                f"  {r['date']}: 정답={r['ground_truth']['category']} "
                f"({r['ground_truth']['reason']}) / "
                f"예측='{r['eval1_detail']['predicted_top_issue'][:50]}'"
            )

    return results


if __name__ == "__main__":
    main()
