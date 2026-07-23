import logging
from datetime import datetime

from db import get_db

logger = logging.getLogger(__name__)


def db_save_node(state: dict) -> dict:
    errors = list(state.get("errors", []))
    db_saved_count = 0
    db_skipped_count = 0

    try:
        report_date_raw = state.get("report_date", "")
        if len(report_date_raw) >= 8:
            report_date = f"{report_date_raw[:4]}-{report_date_raw[4:6]}-{report_date_raw[6:8]}"
        else:
            report_date = report_date_raw

        records = state.get("kpi_summary", {}).get("by_platform", [])
        created_at = datetime.now().isoformat()

        by_product = state.get("kpi_summary", {}).get("by_product", [])

        with get_db() as conn:
            for rec in records:
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO daily_kpi
                        (report_date, channel, platform, zor, zre, net_receipt,
                         hcc_revenue, helinox_revenue, total_revenue,
                         total_point, total_fee, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        report_date,
                        rec.get("channel", ""),
                        rec.get("platform", ""),
                        rec.get("zor", 0),
                        rec.get("zre", 0),
                        rec.get("net_receipt", 0),
                        0.0,
                        0.0,
                        float(rec.get("total_sales", 0)),
                        float(rec.get("total_point", 0)),
                        float(rec.get("total_fee", 0)),
                        created_at,
                    ),
                )
                if cursor.rowcount == 1:
                    db_saved_count += 1
                else:
                    db_skipped_count += 1

            for prod in by_product:
                conn.execute(
                    """INSERT OR IGNORE INTO daily_product
                       (report_date, product_code, product_name,
                        category_l1, category_l2, category_l3,
                        qty, revenue, zre_qty)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        report_date,
                        prod["product_code"],
                        prod["product_name"],
                        "",
                        "",
                        prod.get("category_l3", ""),
                        prod["qty"],
                        prod["total_sales"],
                        prod["zre_qty"],
                    ),
                )

            conn.commit()

        logger.info(f"DB 저장: {db_saved_count}건 신규, {db_skipped_count}건 스킵")
    except Exception as e:
        logger.warning(f"DB 저장 실패: {e}")
        errors.append(f"DB 저장 실패: {e}")

    return {**state, "db_saved_count": db_saved_count, "db_skipped_count": db_skipped_count, "errors": errors}


def db_load_cumulative_node(state: dict) -> dict:
    errors = list(state.get("errors", []))
    kpi_cumulative: dict = {}

    try:
        report_date_raw = state.get("report_date", "")
        if len(report_date_raw) < 6:
            return {**state, "kpi_cumulative": kpi_cumulative, "errors": errors}

        year_month = f"{report_date_raw[:4]}-{report_date_raw[4:6]}"
        like_pattern = f"{year_month}%"

        with get_db() as conn:
            cursor = conn.execute(
                """
                SELECT platform,
                       SUM(zor) as zor, SUM(zre) as zre, SUM(net_receipt) as net_receipt,
                       SUM(hcc_revenue) as hcc_revenue, SUM(helinox_revenue) as helinox_revenue,
                       SUM(total_revenue) as total_revenue,
                       SUM(total_point) as total_point, SUM(total_fee) as total_fee
                FROM daily_kpi
                WHERE report_date LIKE ?
                GROUP BY platform
                """,
                (like_pattern,),
            )
            rows = cursor.fetchall()
            cols = [d[0] for d in cursor.description]
            by_platform = [dict(zip(cols, row)) for row in rows]

            prod_cursor = conn.execute(
                """
                SELECT product_code, product_name, category_l3,
                       SUM(qty) as total_qty,
                       SUM(revenue) as total_revenue,
                       SUM(zre_qty) as total_zre
                FROM daily_product
                WHERE report_date >= date('now', '-30 days')
                GROUP BY product_code
                ORDER BY total_revenue DESC
                LIMIT 30
                """
            )
            prod_rows = prod_cursor.fetchall()
            prod_cols = [d[0] for d in prod_cursor.description]
            top_products_30d = [dict(zip(prod_cols, r)) for r in prod_rows]

        kpi_cumulative = {
            "by_platform": by_platform,
            "month": year_month,
            "top_products_30d": top_products_30d,
        }
        logger.info(
            f"DB 누계 로드: {year_month}, {len(by_platform)}개 플랫폼, "
            f"30일 제품 {len(top_products_30d)}개"
        )
    except Exception as e:
        logger.warning(f"DB 누계 로드 실패: {e}")
        errors.append(f"DB 누계 로드 실패: {e}")

    return {**state, "kpi_cumulative": kpi_cumulative, "errors": errors}
