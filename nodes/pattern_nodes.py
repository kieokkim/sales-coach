import logging
import statistics
from calendar import monthrange
from datetime import datetime, timedelta
from itertools import combinations
import pandas as pd

from config import MONTHLY_TARGETS, PROMOTIONS, DOMAIN_PARAMS, STAT_Z_95
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


def _wilson_lower_bound(successes: int, n: int, z: float = STAT_Z_95) -> float:
    """Wilson score interval 하한. 표본 작으면 넓게 퍼져 하한이 낮아진다."""
    if n == 0:
        return 0.0
    p = successes / n
    denom = 1 + z**2 / n
    center = p + z**2 / (2 * n)
    margin = z * ((p * (1 - p) / n + z**2 / (4 * n**2)) ** 0.5)
    return max(0.0, (center - margin) / denom)


def _return_anomalies(state: dict, report_date_db: str) -> list:
    """
    제품별 반품 이상 탐지 = 유의성(Wilson) AND 효과크기(절대건수 하한).

    - 유의성: 오늘 반품률 Wilson 신뢰구간 하한이 평소(30일) 점추정을 넘는가.
      소표본이면 하한이 넓게 퍼져 자동 보류되어 극단 비율 오탐을 막는다.
    - 효과크기: 오늘 반품 절대수량이 return_min_count 이상인가.
      통계적으로 유의해도(20% vs 2%) 절대량이 사소하면(2건) 운영상 노이즈다.
      Wilson 단독으로는 못 거르는 소량 반품 오탐(0501 케이스)을 이 게이트가 지운다.
    - warm-up: 과거 기준선이 min_baseline_days 미만이면 평소값이 불안정 → 판정 보류.
    """
    by_product = state.get("kpi_summary", {}).get("by_product", [])
    if not by_product:
        return []

    min_count = DOMAIN_PARAMS.get("return_min_count", 5)
    min_days = DOMAIN_PARAMS.get("min_baseline_days", 14)

    try:
        with get_db() as conn:
            cursor = conn.execute(
                """
                SELECT product_code,
                       SUM(qty) as total_qty,
                       SUM(zre_qty) as total_zre,
                       COUNT(DISTINCT report_date) as hist_days
                FROM daily_product
                WHERE report_date >= date(?, '-30 days') AND report_date < ?
                GROUP BY product_code
                """,
                (report_date_db, report_date_db),
            )
            rows = cursor.fetchall()
            # code -> (hist_returns, hist_total, hist_days)
            hist_map = {r[0]: (r[2], r[1] + r[2], r[3]) for r in rows}
    except Exception as e:
        logger.warning(f"return_anomalies DB 조회 실패: {e}")
        hist_map = {}

    anomalies = []
    for prod in by_product:
        code = prod["product_code"]
        today_returns = prod["zre_qty"]
        today_total = prod["qty"] + prod["zre_qty"]
        hist_returns, hist_total, hist_days = hist_map.get(code, (0, 0, 0))

        # 표본이 아예 없으면 판정 불가 (수학적 필수 게이트 — 매직넘버 아님)
        if today_total == 0 or hist_total == 0:
            continue

        # warm-up 게이트: 과거 기준선 부족하면 평소값 불안정 → 판정 보류
        if hist_days < min_days:
            logger.info(
                f"{prod['product_name']}: baseline {hist_days}일 < {min_days}일, 판정 보류"
            )
            continue

        # 효과크기 게이트: 오늘 반품 절대수량 하한 (소량 반품 오탐 제거) ← 핵심
        if today_returns < min_count:
            continue

        hist_rate = hist_returns / hist_total  # 평소 점추정 (기준선)
        today_lower = _wilson_lower_bound(today_returns, today_total)
        today_rate = today_returns / today_total

        # 유의성: 오늘 반품률 신뢰구간 하한이 평소 평균을 넘으면 유의하게 높음
        if today_lower > hist_rate:
            multiplier = round(today_rate / hist_rate, 1) if hist_rate > 0 else 0.0
            anomalies.append({
                "product_name": prod["product_name"],
                "return_rate_today": round(today_rate, 4),
                "return_rate_avg": round(hist_rate, 4),
                "today_lower_bound": round(today_lower, 4),
                "hist_rate": round(hist_rate, 4),
                "today_returns": today_returns,
                "today_sample": today_total,
                "multiplier": multiplier,  # 참고용 (판정엔 안 씀)
                "significance": "Wilson유의+절대건수충족",
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


def _purchase_combo(state: dict) -> dict:
    offline = state.get("offline_processed")
    online = state.get("online_processed")

    dfs = []
    if offline is not None and not offline.empty:
        df = offline[offline["오더유형"] == "ZOR"].copy()
        df["거래키"] = df["고객 참조 번호"]
        dfs.append(df)
    if online is not None and not online.empty:
        df = online[online["오더유형"] == "ZOR"].copy()
        df["거래키"] = df["고객참조번호"]
        dfs.append(df)

    if not dfs:
        return {}

    combined = pd.concat(dfs, ignore_index=True)
    if combined.empty or "대분류내역" not in combined.columns:
        return {}

    try:
        brand_sets = combined.groupby("거래키")["대분류내역"].apply(lambda x: set(x))
        total_orders = len(brand_sets)
        if total_orders == 0:
            return {}

        cross_orders = brand_sets.apply(
            lambda s: "Helinox" in s and "HCC" in s
        ).sum()
        cross_pct = round(cross_orders / total_orders * 100, 1)

        combo_counter: dict = {}
        if "중분류내역" in combined.columns:
            cat_sets = combined.groupby("거래키")["중분류내역"].apply(
                lambda x: sorted(set(x))
            )
            for cats in cat_sets:
                for pair in combinations(cats, 2):
                    combo_counter[pair] = combo_counter.get(pair, 0) + 1

        top_combos = sorted(combo_counter.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "total_orders": total_orders,
            "cross_brand_orders": int(cross_orders),
            "cross_brand_pct": cross_pct,
            "top_category_combos": [
                {"pair": f"{p[0]} + {p[1]}", "count": c}
                for p, c in top_combos
            ],
        }
    except Exception as e:
        logger.warning(f"_purchase_combo 실패: {e}")
        return {}


def _basket_metrics(state: dict) -> dict:
    offline = state.get("offline_processed")
    online = state.get("online_processed")

    result = {}

    try:
        for name, df, ref_col in [
            ("오프라인", offline, "고객 참조 번호"),
            ("온라인", online, "고객참조번호"),
        ]:
            if df is None or df.empty:
                continue
            zor = df[df["오더유형"] == "ZOR"]
            if zor.empty or ref_col not in zor.columns or "매출" not in zor.columns:
                continue

            grouped = zor.groupby(ref_col).agg(
                item_count=("매출", "count"),
                total_amount=("매출", "sum"),
            )

            result[name] = {
                "order_count": len(grouped),
                "avg_items_per_order": round(grouped["item_count"].mean(), 1),
                "avg_amount_per_order": round(grouped["total_amount"].mean()),
            }

        return result
    except Exception as e:
        logger.warning(f"_basket_metrics 실패: {e}")
        return {}


def _time_pattern(state: dict, report_date_db: str) -> dict:
    try:
        d = datetime.strptime(report_date_db, "%Y-%m-%d")
        weekday_idx = d.weekday()
        weekday_name = ["월", "화", "수", "목", "금", "토", "일"][weekday_idx]
        is_weekend = weekday_idx >= 5

        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT report_date, SUM(total_revenue) as daily_total
                FROM daily_kpi
                WHERE report_date >= date(?, '-30 days') AND report_date < ?
                GROUP BY report_date
                """,
                (report_date_db, report_date_db),
            ).fetchall()

        if not rows:
            return {"today_weekday": weekday_name, "is_weekend": is_weekend}

        weekday_totals: dict = {}
        for r in rows:
            rd = datetime.strptime(r[0], "%Y-%m-%d")
            wd = ["월", "화", "수", "목", "금", "토", "일"][rd.weekday()]
            weekday_totals.setdefault(wd, []).append(r[1])

        weekday_avg = {
            wd: round(sum(vals) / len(vals))
            for wd, vals in weekday_totals.items()
        }

        return {
            "today_weekday": weekday_name,
            "is_weekend": is_weekend,
            "weekday_avg_30d": weekday_avg,
            "today_weekday_avg": weekday_avg.get(weekday_name, 0),
        }
    except Exception as e:
        logger.warning(f"_time_pattern 실패: {e}")
        return {}


def _basket_association(state: dict) -> list:
    offline = state.get("offline_processed")
    online = state.get("online_processed")

    dfs = []
    if offline is not None and not offline.empty:
        df = offline[offline["오더유형"] == "ZOR"].copy()
        df["거래키"] = df["고객 참조 번호"]
        dfs.append(df)
    if online is not None and not online.empty:
        df = online[online["오더유형"] == "ZOR"].copy()
        df["거래키"] = df["고객참조번호"]
        dfs.append(df)

    if not dfs:
        return []

    try:
        combined = pd.concat(dfs, ignore_index=True)
        if combined.empty or "제품명" not in combined.columns:
            return []

        baskets = combined.groupby("거래키")["제품명"].apply(
            lambda x: sorted(set(x))
        )
        total_baskets = len(baskets)
        if total_baskets == 0:
            return []

        item_count: dict = {}
        pair_count: dict = {}

        for items in baskets:
            if len(items) > 5:
                items = items[:5]
            for item in items:
                item_count[item] = item_count.get(item, 0) + 1
            for pair in combinations(items, 2):
                pair_count[pair] = pair_count.get(pair, 0) + 1

        results = []
        for (a, b), count in pair_count.items():
            if count < 2:
                continue
            support = round(count / total_baskets, 3)
            confidence_a_to_b = round(count / item_count[a], 3) if item_count.get(a) else 0
            results.append({
                "item_a": a,
                "item_b": b,
                "co_occur_count": count,
                "support": support,
                "confidence": confidence_a_to_b,
            })

        results.sort(key=lambda x: x["confidence"], reverse=True)
        return results[:5]
    except Exception as e:
        logger.warning(f"_basket_association 실패: {e}")
        return []


def _discount_sensitivity(state: dict) -> dict:
    by_product = state.get("kpi_summary", {}).get("by_product", [])
    if not by_product:
        return {}

    try:
        with get_db() as conn:
            master_rows = conn.execute(
                "SELECT product_code, list_price, cost_price FROM product_master"
            ).fetchall()
        price_map = {r[0]: {"list_price": r[1], "cost_price": r[2]} for r in master_rows}

        if not price_map:
            logger.warning("discount_sensitivity: product_master 비어있음")
            return {}

        discount_buckets: dict = {}
        product_discounts = []
        total_margin = 0
        total_revenue = 0

        for prod in by_product:
            code = prod["product_code"]
            qty = prod["qty"]
            revenue = prod["total_sales"]

            info = price_map.get(code)
            if not info or qty == 0:
                continue

            list_price = info["list_price"]
            cost_price = info["cost_price"]

            avg_sell_price = revenue / qty
            discount_pct = round((1 - avg_sell_price / list_price) * 100, 1)
            discount_pct = max(0, discount_pct)

            margin_per_unit = avg_sell_price - cost_price
            margin_total = round(margin_per_unit * qty)
            margin_pct = round(margin_per_unit / avg_sell_price * 100, 1) if avg_sell_price else 0

            total_margin += margin_total
            total_revenue += revenue

            bucket = (
                "0%" if discount_pct < 2 else
                "5%" if discount_pct < 8 else
                "10%" if discount_pct < 13 else
                "15%+"
            )
            discount_buckets.setdefault(bucket, []).append(qty)

            product_discounts.append({
                "product_name": prod["product_name"],
                "discount_pct": discount_pct,
                "qty": qty,
                "revenue": revenue,
                "margin_total": margin_total,
                "margin_pct": margin_pct,
            })

        bucket_summary = {
            bucket: {
                "product_count": len(qtys),
                "avg_qty": round(sum(qtys) / len(qtys), 1),
                "total_qty": sum(qtys),
            }
            for bucket, qtys in discount_buckets.items()
        }

        product_discounts.sort(key=lambda x: x["discount_pct"], reverse=True)
        margin_pct_overall = round(total_margin / total_revenue * 100, 1) if total_revenue else 0

        # 오늘 판매 믹스의 이론 마진 계산
        # (각 제품이 정가로 팔렸다고 가정했을 때의 마진율)
        theoretical_margin_total = 0
        theoretical_revenue_total = 0

        for prod in by_product:
            code = prod["product_code"]
            qty = prod["qty"]
            info = price_map.get(code)
            if not info or qty == 0:
                continue
            list_price = info["list_price"]
            cost_price = info["cost_price"]
            # 정가로 팔렸을 때의 마진 (할인 없다고 가정)
            theoretical_margin_total += (list_price - cost_price) * qty
            theoretical_revenue_total += list_price * qty

        theoretical_margin_pct = (
            round(theoretical_margin_total / theoretical_revenue_total * 100, 1)
            if theoretical_revenue_total > 0 else None
        )

        # 실제 마진과 이론 마진의 편차 (음수면 할인/가격 이슈로 마진 훼손)
        margin_deviation = None
        if theoretical_margin_pct is not None and margin_pct_overall is not None:
            margin_deviation = round(margin_pct_overall - theoretical_margin_pct, 1)

        return {
            "bucket_summary": bucket_summary,
            "top_discounted": product_discounts[:5],
            "total_margin": total_margin,
            "total_revenue": total_revenue,
            "margin_pct_overall": margin_pct_overall,
            "theoretical_margin_pct": theoretical_margin_pct,
            "margin_deviation": margin_deviation,
        }
    except Exception as e:
        logger.warning(f"_discount_sensitivity 실패: {e}")
        return {}


def _trend_direction_30d(state: dict, report_date_db: str) -> dict:
    """
    최근 30일 일별 매출을 전반/후반으로 나눠 장기 방향성을 계산한다.
    7일 평균 대비 오늘(이상치)과 달리 30일 전체 기울기(추세)를 본다.
    """
    try:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT report_date, SUM(total_revenue) as daily_total
                FROM daily_kpi
                WHERE report_date >= date(?, '-30 days')
                  AND report_date < ?
                GROUP BY report_date
                ORDER BY report_date ASC
                """,
                (report_date_db, report_date_db),
            ).fetchall()

        if len(rows) < 7:
            return {}

        mid = len(rows) // 2
        first_half_avg = sum(r[1] for r in rows[:mid]) / mid
        second_half_avg = sum(r[1] for r in rows[mid:]) / (len(rows) - mid)

        if first_half_avg == 0:
            return {}

        change_pct = round((second_half_avg - first_half_avg) / first_half_avg * 100, 1)
        direction = (
            "상승" if change_pct >= 10 else
            "하락" if change_pct <= -10 else
            "횡보"
        )

        with get_db() as conn:
            channel_rows = conn.execute(
                """
                SELECT report_date,
                       SUM(CASE WHEN platform IN ('HCC','HCC 부산점','HCC 제주점')
                           THEN total_revenue ELSE 0 END) as offline_rev,
                       SUM(CASE WHEN platform NOT IN ('HCC','HCC 부산점','HCC 제주점')
                           THEN total_revenue ELSE 0 END) as online_rev
                FROM daily_kpi
                WHERE report_date >= date(?, '-30 days')
                  AND report_date < ?
                GROUP BY report_date
                ORDER BY report_date ASC
                """,
                (report_date_db, report_date_db),
            ).fetchall()

        channel_trends = {}
        for channel, idx in [("오프라인", 1), ("온라인", 2)]:
            vals = [r[idx] for r in channel_rows if r[idx] is not None]
            if len(vals) < 7:
                continue
            mid_c = len(vals) // 2
            f_avg = sum(vals[:mid_c]) / mid_c
            s_avg = sum(vals[mid_c:]) / (len(vals) - mid_c)
            if f_avg == 0:
                continue
            ch_change = round((s_avg - f_avg) / f_avg * 100, 1)
            ch_dir = (
                "상승" if ch_change >= 10 else
                "하락" if ch_change <= -10 else
                "횡보"
            )
            channel_trends[channel] = {
                "direction": ch_dir,
                "change_pct": ch_change,
            }

        # 최근 7일 vs 직전 7일 비교 (가속도)
        # acceleration_pct/라벨은 표시용 유지. 판정은 accel_zscore(회사 변동성 정규화)로.
        accel_zscore = None
        if len(rows) >= 14:
            recent_7 = [r[1] for r in rows[-7:]]
            prev_7 = [r[1] for r in rows[-14:-7]]
            recent_avg = sum(recent_7) / 7
            prev_avg = sum(prev_7) / 7

            # 30일 일별 매출 std 대비 z-score (절대 -15% 문턱 대체)
            daily_sales = [r[1] for r in rows]
            daily_std = statistics.pstdev(daily_sales) if len(daily_sales) >= 2 else 0
            if daily_std > 0:
                accel_zscore = round((recent_avg - prev_avg) / daily_std, 2)

            if prev_avg > 0:
                acceleration_pct = round((recent_avg - prev_avg) / prev_avg * 100, 1)
                if acceleration_pct >= 15:
                    acceleration = "가속상승"
                elif acceleration_pct >= 5:
                    acceleration = "상승중"
                elif acceleration_pct <= -15:
                    acceleration = "가속하락"
                elif acceleration_pct <= -5:
                    acceleration = "하락중"
                else:
                    acceleration = "횡보"
            else:
                acceleration_pct = 0
                acceleration = "측정불가"
        else:
            acceleration_pct = 0
            acceleration = "데이터부족"

        return {
            "overall_direction": direction,
            "overall_change_pct": change_pct,
            "acceleration": acceleration,
            "acceleration_pct": acceleration_pct,
            "accel_zscore": accel_zscore,
            "channel_trends": channel_trends,
            "days_analyzed": len(rows),
        }

    except Exception as e:
        logger.warning(f"_trend_direction_30d 실패: {e}")
        return {}


def _adjusted_daily_target(state: dict, patterns: dict, report_date_raw: str) -> dict:
    """
    요일 가중치 + 프로모션 보정을 반영한 오늘의 조정 일별 목표를 계산한다.
    균등 분할 daily_required 대신 실제 요일 매출 패턴을 반영한 기준을 제공한다.
    """
    try:
        year = int(report_date_raw[:4])
        month = int(report_date_raw[4:6])
        day = int(report_date_raw[6:8])
    except (ValueError, IndexError):
        return {}

    target_summary = state.get("target_summary", {})
    kpi_total = state.get("kpi_total", {})

    raw_daily_required = 0
    for pt in target_summary.get("by_platform", []):
        raw_daily_required += pt.get("daily_required", 0)
    if raw_daily_required == 0:
        return {}

    # daily_required 상한 캡: 남은목표/잔여일 산식은 월말(잔여일→0)에 쌍곡선 발산해
    # 달성불가 목표를 매일 미달로 찍는다. 목표균등(월목표/총일수)의 배수로 상한을 건다.
    # 목표균등 기준이라 데이터 비의존(회사 무관 구조). 배수만 도메인 파라미터.
    year_month = f"{year:04d}-{month:02d}"
    monthly_target = MONTHLY_TARGETS.get(year_month, {}).get("_total", 0)
    total_days_in_month = monthrange(year, month)[1]
    cap_mult = DOMAIN_PARAMS.get("target_daily_cap_multiplier", 1.5)
    if monthly_target > 0 and total_days_in_month > 0:
        daily_cap = cap_mult * (monthly_target / total_days_in_month)
        if raw_daily_required > daily_cap:
            logger.info(
                f"daily_required 캡 적용: {raw_daily_required:,.0f} → {daily_cap:,.0f} "
                f"({cap_mult}×월목표/{total_days_in_month}일)"
            )
            raw_daily_required = daily_cap

    adjustments_applied = []
    adjusted = float(raw_daily_required)

    # 1. 요일 가중치 적용
    dt = datetime(year, month, day)
    weekday_name = ["월", "화", "수", "목", "금", "토", "일"][dt.weekday()]
    weekday_avg = patterns.get("time_pattern", {}).get("weekday_avg_30d", {})

    # 잔여일이 매우 적으면 요일 가중치 생략 (폭발 방지)
    # 잔여 1일이면 raw_daily_required가 남은 목표 전액이 되고
    # 거기에 주말 가중치까지 곱해지면 목표가 비현실적으로 부풀려짐.
    days_remaining_check = monthrange(year, month)[1] - day
    if weekday_avg and len(weekday_avg) >= 5 and days_remaining_check > 3:
        total_week_avg = sum(weekday_avg.values())
        today_weight = weekday_avg.get(weekday_name, 0)
        if total_week_avg > 0 and today_weight > 0:
            uniform_weight = total_week_avg / 7
            weight_ratio = today_weight / uniform_weight
            adjusted = adjusted * weight_ratio
            adjustments_applied.append(
                f"요일 가중치({weekday_name}: ×{weight_ratio:.2f})"
            )
    elif days_remaining_check <= 3:
        adjustments_applied.append("월말 임박 — 요일 가중치 생략")

    # 2. 프로모션 기간 보정
    promo = patterns.get("promo_effect", {})
    if promo.get("active") and promo.get("sales_lift_pct", 0) > 0:
        lift = promo["sales_lift_pct"] / 100
        adjusted = adjusted * (1 + lift)
        adjustments_applied.append(
            f"프로모션 리프트(+{promo['sales_lift_pct']}%)"
        )

    # 3. 월중 위치 효과 (잔여일 기반 심각도)
    days_remaining = total_days_in_month - day

    today_net_sales = kpi_total.get("net_sales", 0)   # 반품 차감 (진짜 실적)
    adjusted_daily_required = int(adjusted)
    achievement_vs_adjusted = (
        round(today_net_sales / adjusted_daily_required * 100, 1)
        if adjusted_daily_required > 0 else 0.0
    )

    threshold = (
        DOMAIN_PARAMS.get("target_shortfall_ratio_early", 0.8)
        if days_remaining >= 7
        else DOMAIN_PARAMS.get("target_shortfall_ratio_late", 0.6)
    )
    if today_net_sales < adjusted_daily_required * threshold:
        if days_remaining < 7:
            severity = "high"
        elif days_remaining < 14:
            severity = "medium"
        else:
            severity = "low"
    else:
        severity = "none"

    # 월말 최후 안전판: 캡 후에도 잔여 소수일은 달성불가 목표라 목표미달 보류.
    skip_days = DOMAIN_PARAMS.get("target_skip_last_days", 3)
    if severity != "none" and days_remaining <= skip_days:
        logger.info(f"월말 {days_remaining}일 ≤ {skip_days}일, 목표미달 판정 보류")
        severity = "none"

    return {
        "raw_daily_required": int(raw_daily_required),
        "adjusted_daily_required": adjusted_daily_required,
        "today_net_sales": today_net_sales,
        "achievement_vs_adjusted": achievement_vs_adjusted,
        "days_remaining": days_remaining,
        "today_weekday": weekday_name,
        "severity": severity,
        "adjustments_applied": adjustments_applied,
    }


def pattern_detect_node(state: dict) -> dict:
    errors = list(state.get("errors", []))
    patterns: dict = {
        "channel_trends": [],
        "category_movers": [],
        "return_anomalies": [],
        "forecast": {},
        "promo_effect": {},
        "purchase_combo": {},
        "basket_metrics": {},
        "time_pattern": {},
        "basket_association": [],
        "discount_sensitivity": {},
        "trend_direction_30d": {},
        "adjusted_daily_target": {},
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

    try:
        patterns["purchase_combo"] = _purchase_combo(state)
    except Exception as e:
        logger.warning(f"purchase_combo 실패: {e}")

    try:
        patterns["basket_metrics"] = _basket_metrics(state)
    except Exception as e:
        logger.warning(f"basket_metrics 실패: {e}")

    try:
        patterns["time_pattern"] = _time_pattern(state, report_date_db)
    except Exception as e:
        logger.warning(f"time_pattern 실패: {e}")

    try:
        patterns["basket_association"] = _basket_association(state)
    except Exception as e:
        logger.warning(f"basket_association 실패: {e}")

    try:
        patterns["discount_sensitivity"] = _discount_sensitivity(state)
    except Exception as e:
        logger.warning(f"discount_sensitivity 실패: {e}")

    try:
        patterns["trend_direction_30d"] = _trend_direction_30d(state, report_date_db)
    except Exception as e:
        logger.warning(f"trend_direction_30d 실패: {e}")

    try:
        patterns["adjusted_daily_target"] = _adjusted_daily_target(state, patterns, report_date_raw)
    except Exception as e:
        logger.warning(f"adjusted_daily_target 실패: {e}")

    logger.info(
        f"pattern_detect 완료: forecast={bool(patterns['forecast'])}, "
        f"return_anomalies={len(patterns['return_anomalies'])}건, "
        f"category_movers={len(patterns['category_movers'])}건, "
        f"basket_association={len(patterns['basket_association'])}건, "
        f"discount_sensitivity={bool(patterns['discount_sensitivity'])}, "
        f"trend_30d={patterns['trend_direction_30d'].get('overall_direction', 'N/A')}"
    )
    return {**state, "patterns": patterns}
