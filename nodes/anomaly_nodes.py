import logging

logger = logging.getLogger(__name__)

HIGH_FEE_RATIO_THRESHOLD = 0.10


def anomaly_detect_node(state: dict) -> dict:
    errors = list(state.get("errors", []))
    anomalies: list[dict] = []

    try:
        report_date = state.get("report_date", "")
        kpi_records = state.get("kpi_summary", {}).get("by_platform", [])

        for rec in kpi_records:
            platform = rec["platform"]
            sales = rec.get("total_sales", 0)
            net_receipt = rec.get("net_receipt", 0)
            total_fee = rec.get("total_fee", 0)

            if sales == 0:
                anomalies.append(
                    {
                        "type": "zero_sales",
                        "platform": platform,
                        "date": report_date,
                        "message": f"{platform}: 해당 일자 매출이 0원입니다.",
                        "severity": "warning",
                    }
                )

            if net_receipt < 0:
                anomalies.append(
                    {
                        "type": "negative_net_receipt",
                        "platform": platform,
                        "date": report_date,
                        "message": f"{platform}: 순영수증이 음수입니다 ({net_receipt:,}건). 반품이 판매보다 많습니다.",
                        "severity": "warning",
                    }
                )

            if sales > 0 and total_fee / sales > HIGH_FEE_RATIO_THRESHOLD:
                ratio_pct = round(total_fee / sales * 100, 1)
                anomalies.append(
                    {
                        "type": "high_fee_ratio",
                        "platform": platform,
                        "date": report_date,
                        "message": f"{platform}: 봉사료 비율이 {ratio_pct}%로 기준(10%)을 초과합니다.",
                        "severity": "info",
                    }
                )

        # 타겟 달성률 낮은 플랫폼
        target_summary = state.get("target_summary", {})
        for pt in target_summary.get("by_platform", []):
            if pt.get("flag") == "low_achievement":
                anomalies.append(
                    {
                        "type": "low_achievement",
                        "platform": pt["platform"],
                        "date": report_date,
                        "message": (
                            f"{pt['platform']}: 월 달성률 {pt['achievement_pct']}%로 "
                            f"기준(70%) 미달. 잔여 {target_summary.get('days_remaining', 0)}일간 "
                            f"일평균 {pt['daily_required']:,}원 필요."
                        ),
                        "severity": "warning",
                    }
                )

        logger.info(f"이상치 탐지 완료: {len(anomalies)}건")
    except Exception as e:
        logger.warning(f"이상치 탐지 실패: {e}")
        errors.append(f"이상치 탐지 실패: {e}")

    return {**state, "anomalies": anomalies, "errors": errors}
