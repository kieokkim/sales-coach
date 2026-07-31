#!/usr/bin/env python3
"""헬리녹스 실제 ERP export 파일 백필 — 과거 KPI/제품집계만 DB에 채운다.

오프라인·온라인 export 파일(여러 날짜 혼재)을 받아 날짜별로 순회하며
report_date 필터(_preprocess_offline/_preprocess_online 기존 로직) → KPI 계산
(_compute_kpi_for/_compute_by_product, seed_db.py와 동일한 저수준 함수 재사용) →
daily_kpi/daily_product 저장만 수행한다.

graph 전체나 LLM 3개 노드(insight/action/commentary), anomaly_detect/
pattern_detect/target_compare는 호출하지 않는다 — 백필은 과거 KPI 수치만
쌓으면 되고 그날그날의 판단/리포트는 불필요.

channel은 매장/플랫폼명이 아니라 파일 출처 기준(오프라인 파일→오프라인,
온라인 파일→온라인)으로 처음부터 태깅한다 — backfill_channel.py 같은
소급 스크립트가 다시 필요없게.

멱등: INSERT OR IGNORE 컨벤션 그대로 사용, 여러 번 실행해도 안전.
"""
import argparse
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from db import get_db, init_db
from config import DOMAIN_PARAMS
from nodes.kpi_nodes import _compute_by_product, _compute_kpi_for
from nodes.preprocess_nodes import _normalize_date_col, _preprocess_offline, _preprocess_online

# 이 백필이 실제로 계산하는 것(_compute_kpi_for/_compute_by_product)에
# 필요한 컬럼만 검증한다. 오더사유명은 return_reason_breakdown 전용이라
# pattern_detect를 호출하지 않는 이 경로엔 불필요 — 검증 대상에서 제외.
OFFLINE_REQUIRED = ["오더유형", "제품코드", "제품명"]
ONLINE_REQUIRED = ["오더유형", "판매처명", "제품코드", "제품명"]


def _require_columns(df: pd.DataFrame, required: list, label: str, path: str):
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"{label} 파일 필수 컬럼 누락: {missing} (파일: {path}, "
            f"실제 컬럼: {list(df.columns)})"
        )


def _require_one_of(df: pd.DataFrame, candidates: list, label: str, path: str):
    if not any(c in df.columns for c in candidates):
        raise ValueError(
            f"{label} 파일에 {candidates} 중 컬럼 하나도 없음 (파일: {path}, "
            f"실제 컬럼: {list(df.columns)})"
        )


def _validate_offline(df: pd.DataFrame, path: str):
    _require_columns(df, OFFLINE_REQUIRED, "오프라인", path)
    _require_one_of(df, ["판매일자", "고객 참조 번호"], "오프라인", path)
    _require_one_of(df, ["매출", "S/O sum"], "오프라인", path)
    _require_one_of(df, ["수량", "S/O수량"], "오프라인", path)


def _validate_online(df: pd.DataFrame, path: str):
    _require_columns(df, ONLINE_REQUIRED, "온라인", path)
    _require_one_of(df, ["청구일", "판매일자"], "온라인", path)
    _require_one_of(df, ["매출", "총금액"], "온라인", path)
    _require_one_of(df, ["수량", "청구수량"], "온라인", path)


def _extract_dates(offline_raw: pd.DataFrame, online_raw: pd.DataFrame) -> list:
    dates = set()
    if offline_raw is not None:
        if "판매일자" in offline_raw.columns and offline_raw["판매일자"].notna().any():
            dates |= set(_normalize_date_col(offline_raw["판매일자"]))
        else:
            dates |= set(offline_raw["고객 참조 번호"].astype(str).str[9:17])
    if online_raw is not None:
        if "청구일" in online_raw.columns and online_raw["청구일"].notna().any():
            dates |= set(_normalize_date_col(online_raw["청구일"]))
        elif "판매일자" in online_raw.columns and online_raw["판매일자"].notna().any():
            dates |= set(_normalize_date_col(online_raw["판매일자"]))

    valid = sorted(d for d in dates if len(d) == 8 and d.isdigit() and d.startswith("20"))
    return valid


def _verify_baseline_gate(last_date_db: str):
    """반품 이상탐지(_return_anomalies)와 동일한 hist_days 쿼리로
    min_baseline_days 게이트가 실제로 열리는지 사전 확인."""
    next_date_db = (
        datetime.strptime(last_date_db, "%Y-%m-%d") + timedelta(days=1)
    ).strftime("%Y-%m-%d")

    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT product_code,
                   SUM(qty) as total_qty,
                   SUM(zre_qty) as total_zre,
                   COUNT(DISTINCT report_date) as hist_days
            FROM daily_product
            WHERE report_date >= date(?, '-30 days') AND report_date < ?
            GROUP BY product_code
            """,
            (next_date_db, next_date_db),
        ).fetchall()

    min_days = DOMAIN_PARAMS.get("min_baseline_days", 14)
    max_hist_days = max((r[3] for r in rows), default=0)
    gate_open = max_hist_days >= min_days
    print(
        f"\n검증(hist_days, 기준일 {next_date_db}): 제품 {len(rows)}개, "
        f"최대 누적 {max_hist_days}일 (min_baseline_days={min_days}) "
        f"→ 게이트 {'열림' if gate_open else '닫힘'}"
    )


def run(offline_path: str = None, online_path: str = None):
    if not offline_path and not online_path:
        raise ValueError("offline_path 또는 online_path 중 최소 하나는 필요")

    init_db()

    offline_raw = None
    online_raw = None
    if offline_path:
        offline_raw = pd.read_excel(offline_path)
        _validate_offline(offline_raw, offline_path)
    if online_path:
        online_raw = pd.read_excel(online_path)
        _validate_online(online_raw, online_path)

    dates = _extract_dates(offline_raw, online_raw)
    if not dates:
        raise ValueError("날짜 추출 실패 — 판매일자/청구일/고객 참조 번호 컬럼 형식 확인 필요")

    print(f"날짜 범위: {dates[0]} ~ {dates[-1]} ({len(dates)}일)")

    inserted_kpi = 0
    inserted_product = 0
    skipped = 0
    created_at = datetime.now().isoformat()

    for date_str in dates:
        date_db = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

        try:
            off = _preprocess_offline(offline_raw.copy(), date_str) if offline_raw is not None else pd.DataFrame()
            on = _preprocess_online(online_raw.copy(), date_str) if online_raw is not None else pd.DataFrame()
        except Exception as e:
            raise RuntimeError(f"{date_db} 전처리 중 실패: {e}") from e

        if off.empty and on.empty:
            continue

        all_kpi = []
        if not off.empty:
            all_kpi.extend(_compute_kpi_for(off, channel="오프라인"))
        if not on.empty:
            all_kpi.extend(_compute_kpi_for(on, channel="온라인"))

        dfs = [df for df in [off, on] if not df.empty]
        combined = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
        by_product = _compute_by_product(combined, top_n=50) if not combined.empty else []

        date_revenue = 0
        with get_db() as conn:
            for rec in all_kpi:
                cursor = conn.execute(
                    """INSERT OR IGNORE INTO daily_kpi
                       (report_date, channel, platform,
                        zor, zre, net_receipt,
                        hcc_revenue, helinox_revenue, total_revenue,
                        total_point, total_fee, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        date_db, rec["channel"], rec["platform"],
                        rec["zor"], rec["zre"], rec["net_receipt"],
                        0.0, 0.0, float(rec["total_sales"]),
                        float(rec["total_point"]), float(rec["total_fee"]),
                        created_at,
                    ),
                )
                if cursor.rowcount == 1:
                    inserted_kpi += 1
                else:
                    skipped += 1
                date_revenue += rec["total_sales"]

            for prod in by_product:
                cursor = conn.execute(
                    """INSERT OR IGNORE INTO daily_product
                       (report_date, product_code, product_name,
                        category_l1, category_l2, category_l3,
                        qty, revenue, zre_qty)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        date_db,
                        prod["product_code"], prod["product_name"],
                        "", "", prod.get("category_l3", ""),
                        prod["qty"], prod["total_sales"], prod["zre_qty"],
                    ),
                )
                if cursor.rowcount == 1:
                    inserted_product += 1
                else:
                    skipped += 1

            conn.commit()

        print(f"  {date_db}: {len(all_kpi)}개 플랫폼, 합계매출 {date_revenue:,}원")

    print(f"\n완료: daily_kpi {inserted_kpi}건 / daily_product {inserted_product}건 적재, 스킵(중복) {skipped}건")

    _verify_baseline_gate(f"{dates[-1][:4]}-{dates[-1][4:6]}-{dates[-1][6:8]}")


def main():
    parser = argparse.ArgumentParser(description="헬리녹스 ERP export 파일 백필 (KPI만, 판단 없음)")
    parser.add_argument("--offline", help="오프라인 export 파일 경로")
    parser.add_argument("--online", help="온라인 export 파일 경로")
    args = parser.parse_args()
    run(offline_path=args.offline, online_path=args.online)


if __name__ == "__main__":
    main()
