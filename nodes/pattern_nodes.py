import logging
from calendar import monthrange
from datetime import datetime, timedelta

from config import MONTHLY_TARGETS, PROMOTIONS
from db import get_db

logger = logging.getLogger(__name__)


def _channel_trends(state: dict, report_date_db: str) -> list:
    today_by_platform = state.get("kpi_summary", {}).get("by_platform", [])
    if not today_by_platform:
        return []

    try:
        with get_db() as conn:
            cursor = conn.execute(
                """
                SELECT report_date, SUM(total_revenue) as daily_total
                FROM daily_kpi
                WHERE report_date < ?
                GROUP BY report_date
                ORDER BY report_date DESC
                LIMIT 7
                """,
                (report_date_db,),
            )
            rows = cursor.fetchall()
    except Exception as e:
        logger.warning(f"channel_trends DB 조회 실패: {e}")
        return []

    today_total = sum(r["total_sales"] for r in today_by_platform)

    if not rows:
        # DB 이력 없어도 오늘 수치 반환
        if today_total == 0:
            return []
        return [{
            "channel": "전체",
            "today": today_total,
            "seven_day_avg": 0,
            "change_pct": 0.0,
            "flag": "비교불가 (이력 없음)",
        }]

    seven_day_avg = sum(r[1] for r in rows) / len(rows)

    if seven_day_avg == 0:
        # DB 이력 없어도 오늘 수치는 반환
        return [{
            "channel": "전체",
            "today": today_total,
            "seven_day_avg": 0,
            "change_pct": 0.0,
            "flag": "비교불가 (이력 없음)",
        }]

    change_pct = round((today_total - seven_day_avg) / seven_day_avg * 100, 1)
    flag = (
        "급락" if change_pct <= -30 else
        "하락" if change_pct < -10 else
        "상승" if change_pct >= 10 else
        "보합"
    )
    return [{
        "channel": "전체",
        "today": today_total,
        "seven_day_avg": round(seven_day_avg),
        "change_pct": change_pct,
        "flag": flag,
    }]


def _category_movers(state: dict) -> list:
    by_category = state.get("kpi_summary", {}).get("by_category", [])
    if not by_category:
        return []

    l1_totals: dict = {}
    grand_total = 0
    for item in by_category:
        l1 = item["category_l1"]
        l1_totals[l1] = l1_totals.get(l1, 0) + item["total_sales"]
        grand_total += item["total_sales"]

    if grand_total == 0:
        return []

    movers = []
    for l1, total in sorted(l1_totals.items(), key=lambda x: x[1], reverse=True):
        share_pct = round(total / grand_total * 100, 1)
        movers.append({
            "category_l1": l1,
            "total_sales": total,
            "share_pct": share_pct,
            "flag": share_pct > 50,
        })
    return movers


def _return_anomalies(state: dict, report_date_db: str) -> list:
    by_product = state.get("kpi_summary", {}).get("by_product", [])
    if not by_product:
        return []

    try:
        with get_db() as conn:
            cursor = conn.execute(
                """
                SELECT product_code,
                       SUM(qty) as total_qty,
                       SUM(zre_qty) as total_zre
                FROM daily_product
                WHERE report_date >= date(?, '-30 days') AND report_date < ?
                GROUP BY product_code
                """,
                (report_date_db, report_date_db),
            )
            rows = cursor.fetchall()
            avg_rates = {
                r[0]: (r[2] / (r[1] + r[2]) if (r[1] + r[2]) > 0 else 0)
                for r in rows
            }
    except Exception as e:
        logger.warning(f"return_anomalies DB 조회 실패: {e}")
        avg_rates = {}

    anomalies = []
    for prod in by_product:
        code = prod["product_code"]
        qty = prod["qty"]
        zre = prod["zre_qty"]
        total = qty + zre
        if total == 0:
            continue
        today_rate = zre / total
        avg_rate = avg_rates.get(code, 0)
        multiplier = round(today_rate / avg_rate, 1) if avg_rate > 0 else 0.0
        flag = multiplier >= 3 and today_rate > 0.1
        if flag:
            anomalies.append({
                "product_name": prod["product_name"],
                "return_rate_today": round(today_rate, 3),
                "return_rate_avg": round(avg_rate, 3),
                "multiplier": multiplier,
                "flag": True,
            })
    return anomalies


def _forecast(state: dict, report_date_raw: str) -> dict:
    # kpi_cumulative 대신 DB에서 이번달 누적만 직접 조회
    try:
        year = int(report_date_raw[:4])
        month = int(report_date_raw[4:6])
        day = int(report_date_raw[6:8])
    except (ValueError, IndexError):
        return {}

    total_days = monthrange(year, month)[1]
    days_remaining = total_days - day
    year_month = f"{year:04d}-{month:02d}"
    month_prefix = f"{year:04d}-{month:02d}"  # DB는 YYYY-MM-DD 형식

    try:
        with get_db() as conn:
            # 이번달 누적만 조회
            rows = conn.execute(
                """
                SELECT report_date, SUM(total_revenue) as daily_total
                FROM daily_kpi
                WHERE report_date LIKE ? || '%'
                GROUP BY report_date
                ORDER BY report_date
                """,
                (month_prefix,),
            ).fetchall()
    except Exception as e:
        logger.warning(f"forecast DB 조회 실패: {e}")
        return {}

    if not rows:
        return {}

    current_total = sum(r[1] for r in rows)
    daily_avg = round(current_total / len(rows))  # 실제 영업일 기준
    forecast_total = current_total + daily_avg * days_remaining
    target = MONTHLY_TARGETS.get(year_month, {}).get("_total", 0)
    forecast_achievement_pct = (
        round(forecast_total / target * 100, 1) if target > 0 else 0.0
    )

    return {
        "current_total": current_total,
        "daily_avg": daily_avg,
        "days_remaining": days_remaining,
        "forecast_total": forecast_total,
        "target": target,
        "forecast_achievement_pct": forecast_achievement_pct,
    }


def _promo_effect(state: dict, report_date_raw: str) -> dict:
    year = report_date_raw[:4]
    month = report_date_raw[4:6]
    month_key = f"{year}-{month}"

    active_promos = [
        p for p in PROMOTIONS.get(month_key, [])
        if p["start"] <= report_date_raw <= p["end"]
    ]
    if not active_promos:
        return {"active": False}

    promo = active_promos[0]

    try:
        start_dt = datetime.strptime(promo["start"], "%Y%m%d")
        pre_start = (start_dt - timedelta(days=7)).strftime("%Y-%m-%d")
        pre_end = (start_dt - timedelta(days=1)).strftime("%Y-%m-%d")
        promo_start_fmt = start_dt.strftime("%Y-%m-%d")
        report_date_fmt = f"{report_date_raw[:4]}-{report_date_raw[4:6]}-{report_date_raw[6:8]}"

        with get_db() as conn:
            pre_rows = conn.execute(
                "SELECT SUM(total_revenue) FROM daily_kpi WHERE report_date BETWEEN ? AND ? GROUP BY report_date",
                (pre_start, pre_end),
            ).fetchall()
            during_rows = conn.execute(
                "SELECT SUM(total_revenue) FROM daily_kpi WHERE report_date BETWEEN ? AND ? GROUP BY report_date",
                (promo_start_fmt, report_date_fmt),
            ).fetchall()

        pre_avg = sum(r[0] for r in pre_rows if r[0]) / len(pre_rows) if pre_rows else 0
        during_avg = sum(r[0] for r in during_rows if r[0]) / len(during_rows) if during_rows else 0
        lift = round((during_avg - pre_avg) / pre_avg * 100, 1) if pre_avg > 0 else 0.0

        return {"active": True, "name": promo["name"], "sales_lift_pct": lift, "return_lift_pct": 0.0}
    except Exception as e:
        logger.warning(f"promo_effect 계산 실패: {e}")
        return {"active": True, "name": promo["name"], "sales_lift_pct": 0.0, "return_lift_pct": 0.0}


def pattern_detect_node(state: dict) -> dict:
    errors = list(state.get("errors", []))
    patterns: dict = {
        "channel_trends": [],
        "category_movers": [],
        "return_anomalies": [],
        "forecast": {},
        "promo_effect": {},
    }

    report_date_raw = state.get("report_date", "")
    if len(report_date_raw) < 8:
        logger.warning("pattern_detect: report_date 없음, 스킵")
        return {**state, "patterns": patterns}

    report_date_db = f"{report_date_raw[:4]}-{report_date_raw[4:6]}-{report_date_raw[6:8]}"

    try:
        patterns["channel_trends"] = _channel_trends(state, report_date_db)
    except Exception as e:
        logger.warning(f"channel_trends 실패: {e}")

    try:
        patterns["category_movers"] = _category_movers(state)
    except Exception as e:
        logger.warning(f"category_movers 실패: {e}")

    try:
        patterns["return_anomalies"] = _return_anomalies(state, report_date_db)
    except Exception as e:
        logger.warning(f"return_anomalies 실패: {e}")

    try:
        patterns["forecast"] = _forecast(state, report_date_raw)
    except Exception as e:
        logger.warning(f"forecast 실패: {e}")

    try:
        patterns["promo_effect"] = _promo_effect(state, report_date_raw)
    except Exception as e:
        logger.warning(f"promo_effect 실패: {e}")

    logger.info(
        f"pattern_detect 완료: forecast={bool(patterns['forecast'])}, "
        f"return_anomalies={len(patterns['return_anomalies'])}건, "
        f"category_movers={len(patterns['category_movers'])}건"
    )
    return {**state, "patterns": patterns}
