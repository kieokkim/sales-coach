#!/usr/bin/env python3
"""
샘플 데이터 DB 사전 적재 스크립트

실행 순서:
  1. uv run python scripts/seed_db.py
  2. uv run streamlit run streamlit_app.py
  3. 업로드 페이지에서 sample_offline_3months.xlsx / sample_online_3months.xlsx 업로드
  4. 원하는 날짜 선택 → 리포트 생성 (7일/30일 비교 데이터가 DB에 있어야 정상 작동)

주의: 이 스크립트는 멱등(idempotent)합니다.
      이미 적재된 날짜는 INSERT OR IGNORE로 스킵됩니다.
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from db import get_db, init_db
from nodes.kpi_nodes import _compute_by_product, _compute_kpi_for
from nodes.preprocess_nodes import _preprocess_offline, _preprocess_online

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
OFFLINE_FILE = os.path.join(DATA_DIR, "sample_offline_3months.xlsx")
ONLINE_FILE = os.path.join(DATA_DIR, "sample_online_3months.xlsx")


def seed_product_master():
    master_path = os.path.join(DATA_DIR, "product_master.xlsx")
    master_df = pd.read_excel(master_path)

    with get_db() as conn:
        existing = conn.execute(
            "SELECT COUNT(*) FROM product_master"
        ).fetchone()[0]
        if existing > 0:
            print(f"product_master 이미 적재됨 ({existing}건), 스킵")
            return

        count = 0
        for _, row in master_df.iterrows():
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO product_master
                       (product_code, product_name, category_l1,
                        category_l2, category_l3, list_price, cost_price)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (row["제품코드"], row["제품명"], row["대분류내역"],
                     row["중분류내역"], row["소분류내역"],
                     int(row["단가"]), int(row["원가"]))
                )
                count += 1
            except Exception as e:
                print(f"제품 적재 실패: {row.get('제품코드', '?')} - {e}")
        print(f"product_master: {count}건 적재")


def seed():
    init_db()
    seed_product_master()

    print("파일 로드 중...")
    offline_raw = pd.read_excel(OFFLINE_FILE)
    online_raw = pd.read_excel(ONLINE_FILE)

    # 오프라인 기준으로 날짜 범위 추출 (판매일자 컬럼 우선, 없으면 참조번호 fallback)
    if "판매일자" in offline_raw.columns and offline_raw["판매일자"].notna().any():
        dates = sorted(offline_raw["판매일자"].astype(str).str.zfill(8).unique())
    else:
        dates = sorted(offline_raw["고객 참조 번호"].astype(str).str[9:17].unique())
    dates = [d for d in dates if len(d) == 8 and d.isdigit() and d.startswith("20")]

    if not dates:
        print("ERROR: 날짜 추출 실패. '고객 참조 번호' 컬럼 형식을 확인하세요.")
        sys.exit(1)

    print(f"날짜 범위: {dates[0]} ~ {dates[-1]} ({len(dates)}일)")

    inserted_kpi = 0
    inserted_product = 0
    skipped = 0
    created_at = datetime.now().isoformat()

    for idx, date_str in enumerate(dates):
        date_db = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

        off = _preprocess_offline(offline_raw.copy(), date_str)
        on = _preprocess_online(online_raw.copy(), date_str)

        if off.empty and on.empty:
            continue

        # 플랫폼별 KPI
        all_kpi: list = []
        if not off.empty:
            all_kpi.extend(_compute_kpi_for(off, channel="오프라인"))
        if not on.empty:
            all_kpi.extend(_compute_kpi_for(on, channel="온라인"))

        # 제품별 집계
        dfs = [df for df in [off, on] if not df.empty]
        combined = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
        by_product = _compute_by_product(combined, top_n=50) if not combined.empty else []

        with get_db() as conn:
            for rec in all_kpi:
                try:
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
                except Exception as e:
                    print(f"  [WARN] daily_kpi 적재 실패 ({date_db}): {e}")
                    skipped += 1

            for prod in by_product:
                try:
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
                except Exception as e:
                    print(f"  [WARN] daily_product 적재 실패 ({date_db}): {e}")
                    skipped += 1

            conn.commit()

        if (idx + 1) % 10 == 0 or idx == len(dates) - 1:
            print(f"  {date_str} 처리 완료 ({idx + 1}/{len(dates)})")

    print(f"\n완료:")
    print(f"  daily_kpi: {inserted_kpi}건 적재")
    print(f"  daily_product: {inserted_product}건 적재")
    print(f"  스킵(중복): {skipped}건")


if __name__ == "__main__":
    seed()
