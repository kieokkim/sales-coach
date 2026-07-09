import logging
from calendar import monthrange
from datetime import datetime

from config import MONTHLY_TARGETS, DOMAIN_PARAMS

logger = logging.getLogger(__name__)

# 문턱은 config.DOMAIN_PARAMS(single source of truth). 근거는 COMPANY_PROFILE.md.
LOW_ACHIEVEMENT_THRESHOLD = DOMAIN_PARAMS.get("target_low_achievement_pct", 70.0)


def target_compare_node(state: dict) -> dict:
    errors = list(state.get("errors", []))
    target_summary: dict = {}

    try:
        report_date = state.get("report_date", "")
        if len(report_date) < 6:
            logger.warning("report_date 형식이 잘못되어 타겟 비교를 건너뜁니다.")
            return {**state, "target_summary": target_summary, "errors": errors}

        year = int(report_date[:4])
        month = int(report_date[4:6])
        month_key = f"{year}-{month:02d}"

        targets = MONTHLY_TARGETS.get(month_key)
        if not targets:
            logger.info(f"{month_key} 타겟 미설정, 타겟 비교 생략")
            return {**state, "target_summary": target_summary, "errors": errors}

        total_target = targets.get("_total", 0)
        if total_target == 0:
            return {**state, "target_summary": target_summary, "errors": errors}

        # 기준일까지 경과 일수 / 잔여 일수
        day_of_month = int(report_date[6:8]) if len(report_date) >= 8 else 1
        total_days = monthrange(year, month)[1]
        days_remaining = max(total_days - day_of_month, 0)

        kpi_cumulative = state.get("kpi_cumulative", {})
        if kpi_cumulative and kpi_cumulative.get("by_platform"):
            cumulative_records = kpi_cumulative["by_platform"]
            total_actual = int(sum(r.get("total_revenue", 0) for r in cumulative_records))
            platform_actual_map = {r["platform"]: int(r.get("total_revenue", 0)) for r in cumulative_records}
        else:
            kpi_total = state.get("kpi_total", {})
            total_actual = kpi_total.get("total_sales", 0)
            kpi_records = state.get("kpi_summary", {}).get("by_platform", [])
            platform_actual_map = {rec["platform"]: rec["total_sales"] for rec in kpi_records}

        total_achievement_pct = round(total_actual / total_target * 100, 1) if total_target else 0
        remaining_amount = max(total_target - total_actual, 0)
        daily_required = int(remaining_amount / days_remaining) if days_remaining > 0 else 0

        by_platform = []

        for platform, platform_target in targets.items():
            if platform == "_total" or platform_target == 0:
                continue
            actual = platform_actual_map.get(platform, 0)
            achievement_pct = round(actual / platform_target * 100, 1)
            p_remaining = max(platform_target - actual, 0)
            p_daily_required = int(p_remaining / days_remaining) if days_remaining > 0 else 0
            flag = "low_achievement" if achievement_pct < LOW_ACHIEVEMENT_THRESHOLD else None

            by_platform.append(
                {
                    "platform": platform,
                    "target": platform_target,
                    "actual": actual,
                    "achievement_pct": achievement_pct,
                    "daily_required": p_daily_required,
                    "flag": flag,
                }
            )

        target_summary = {
            "month": month_key,
            "total_target": total_target,
            "total_actual": total_actual,
            "total_achievement_pct": total_achievement_pct,
            "days_remaining": days_remaining,
            "daily_required": daily_required,
            "by_platform": by_platform,
        }

        logger.info(f"타겟 비교 완료: {month_key} 달성률 {total_achievement_pct}%")
    except Exception as e:
        logger.warning(f"타겟 비교 실패: {e}")
        errors.append(f"타겟 비교 실패: {e}")

    return {**state, "target_summary": target_summary, "errors": errors}
