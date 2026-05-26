import logging
import pandas as pd

logger = logging.getLogger(__name__)


def _compute_kpi_for(df: pd.DataFrame, platform_col: str = "판매처명") -> list[dict]:
    if df.empty:
        return []

    records = []
    for platform, grp in df.groupby(platform_col):
        zor = len(grp[grp["오더유형"] == "ZOR"])
        zre = len(grp[grp["오더유형"] == "ZRE"])
        net_receipt = zor - zre

        total_sales = grp["매출"].sum() if "매출" in grp.columns else 0
        total_point = grp["포인트"].sum() if "포인트" in grp.columns else 0
        total_fee = grp["봉사료"].sum() if "봉사료" in grp.columns else 0

        records.append(
            {
                "platform": str(platform),
                "zor": zor,
                "zre": zre,
                "net_receipt": net_receipt,
                "total_sales": int(total_sales),
                "total_point": int(total_point),
                "total_fee": int(total_fee),
            }
        )
    return records


def kpi_compute_node(state: dict) -> dict:
    errors = list(state.get("errors", []))
    kpi_summary = {"by_platform": []}
    kpi_total = {
        "net_receipt": 0,
        "total_sales": 0,
        "total_point": 0,
        "total_fee": 0,
    }

    try:
        offline = state.get("offline_processed")
        online = state.get("online_processed")

        all_records = []

        if offline is not None and not offline.empty:
            all_records.extend(_compute_kpi_for(offline))

        if online is not None and not online.empty:
            all_records.extend(_compute_kpi_for(online))

        # 같은 플랫폼이 오프/온라인에 겹치는 경우 합산
        merged: dict[str, dict] = {}
        for rec in all_records:
            p = rec["platform"]
            if p not in merged:
                merged[p] = rec.copy()
            else:
                for key in ["zor", "zre", "net_receipt", "total_sales", "total_point", "total_fee"]:
                    merged[p][key] += rec[key]

        by_platform = list(merged.values())
        kpi_summary["by_platform"] = by_platform

        for rec in by_platform:
            kpi_total["net_receipt"] += rec["net_receipt"]
            kpi_total["total_sales"] += rec["total_sales"]
            kpi_total["total_point"] += rec["total_point"]
            kpi_total["total_fee"] += rec["total_fee"]

        logger.info(f"KPI 집계 완료: {len(by_platform)}개 플랫폼, 총매출 {kpi_total['total_sales']:,}원")
    except Exception as e:
        logger.warning(f"KPI 집계 실패: {e}")
        errors.append(f"KPI 집계 실패: {e}")

    return {**state, "kpi_summary": kpi_summary, "kpi_total": kpi_total, "errors": errors}
