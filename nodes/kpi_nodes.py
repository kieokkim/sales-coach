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

        zor_df = grp[grp["오더유형"] == "ZOR"]
        zre_df = grp[grp["오더유형"] == "ZRE"]
        total_sales = zor_df["매출"].sum() if "매출" in zor_df.columns else 0
        total_return_sales = zre_df["매출"].sum() if "매출" in zre_df.columns else 0
        net_sales = int(total_sales - total_return_sales)
        total_point = grp["포인트"].sum() if "포인트" in grp.columns else 0
        total_fee = grp["봉사료"].sum() if "봉사료" in grp.columns else 0

        records.append({
            "platform": str(platform),
            "zor": zor,
            "zre": zre,
            "net_receipt": net_receipt,
            "total_sales": int(total_sales),
            "net_sales": net_sales,
            "total_point": int(total_point),
            "total_fee": int(total_fee),
        })
    return records


def _compute_by_category(df: pd.DataFrame) -> list[dict]:
    """대분류 → 중분류 → 소분류 계층별 매출 집계 (ZOR 기준)"""
    if df.empty:
        return []

    required = {"대분류내역", "중분류내역", "소분류내역", "매출", "오더유형"}
    missing = required - set(df.columns)
    if missing:
        logger.warning(f"카테고리 집계 컬럼 부족: {missing}")
        return []

    zor = df[df["오더유형"] == "ZOR"].copy()
    if zor.empty:
        return []

    records = []
    for (l1, l2, l3), grp in zor.groupby(
        ["대분류내역", "중분류내역", "소분류내역"], sort=False
    ):
        records.append({
            "category_l1": str(l1),
            "category_l2": str(l2),
            "category_l3": str(l3),
            "qty": int(grp["수량"].sum()) if "수량" in grp.columns else len(grp),
            "total_sales": int(grp["매출"].sum()),
        })

    records.sort(key=lambda x: x["total_sales"], reverse=True)
    return records


def _compute_by_product(df: pd.DataFrame, top_n: int = 20) -> list[dict]:
    required = {"제품코드", "제품명", "매출", "오더유형"}
    missing = required - set(df.columns)
    if missing:
        logger.warning(f"제품 집계 컬럼 부족: {missing}")
        return []

    zor = df[df["오더유형"] == "ZOR"].copy()
    zre = df[df["오더유형"] == "ZRE"].copy()

    # ZRE 반품 수량 미리 집계 (행 개수가 아닌 수량 합 — 단위 일치)
    if not zre.empty and "수량" in zre.columns:
        zre_count = zre.groupby("제품코드")["수량"].sum().astype(int).to_dict()
    elif not zre.empty:
        logger.warning("ZRE에 수량 컬럼 없음, 행 개수로 대체")
        zre_count = zre.groupby("제품코드").size().to_dict()
    else:
        zre_count = {}

    group_cols = ["제품코드", "제품명"]
    if "소분류내역" in df.columns:
        group_cols.append("소분류내역")

    records = []

    # ZOR 기준 집계 (기존)
    if not zor.empty:
        for keys, grp in zor.groupby(group_cols, sort=False):
            if isinstance(keys, str):
                keys = (keys,)
            product_code = str(keys[0])
            records.append({
                "product_code": product_code,
                "product_name": str(keys[1]),
                "category_l3": str(keys[2]) if len(keys) > 2 else "",
                "qty": int(grp["수량"].sum()) if "수량" in grp.columns else len(grp),
                "total_sales": int(grp["매출"].sum()),
                "zre_qty": zre_count.get(product_code, 0),
            })

    # ZRE만 있는 제품 추가 (오늘 반품만 발생한 케이스)
    if not zre.empty:
        zor_codes = {r["product_code"] for r in records}
        for keys, grp in zre.groupby(group_cols, sort=False):
            if isinstance(keys, str):
                keys = (keys,)
            product_code = str(keys[0])
            if product_code not in zor_codes:
                records.append({
                    "product_code": product_code,
                    "product_name": str(keys[1]),
                    "category_l3": str(keys[2]) if len(keys) > 2 else "",
                    "qty": 0,
                    "total_sales": 0,
                    "zre_qty": int(grp["수량"].sum()) if "수량" in grp.columns else int(len(grp)),
                })

    # ZOR 제품: total_sales 내림차순 top_n개
    # ZRE 전용 제품(total_sales=0): 항상 전량 포함 (반품 이상 감지용)
    zor_records = sorted(
        [r for r in records if r["total_sales"] > 0],
        key=lambda x: x["total_sales"], reverse=True
    )
    zre_only_records = sorted(
        [r for r in records if r["total_sales"] == 0 and r["zre_qty"] > 0],
        key=lambda x: x["zre_qty"], reverse=True
    )
    return zor_records[:top_n] + zre_only_records


def kpi_compute_node(state: dict) -> dict:
    errors = list(state.get("errors", []))
    kpi_summary = {
        "by_platform": [],
        "by_category": [],
        "by_product": [],
    }
    kpi_total = {
        "net_receipt": 0,
        "total_sales": 0,
        "net_sales": 0,
        "total_point": 0,
        "total_fee": 0,
    }

    try:
        offline = state.get("offline_processed")
        online = state.get("online_processed")

        # ── 기존: by_platform ────────────────────────────
        all_records = []
        if offline is not None and not offline.empty:
            all_records.extend(_compute_kpi_for(offline))
        if online is not None and not online.empty:
            all_records.extend(_compute_kpi_for(online))

        merged: dict[str, dict] = {}
        for rec in all_records:
            p = rec["platform"]
            if p not in merged:
                merged[p] = rec.copy()
            else:
                for key in ["zor", "zre", "net_receipt", "total_sales", "net_sales", "total_point", "total_fee"]:
                    merged[p][key] += rec[key]

        by_platform = list(merged.values())
        kpi_summary["by_platform"] = by_platform

        for rec in by_platform:
            kpi_total["net_receipt"] += rec["net_receipt"]
            kpi_total["total_sales"] += rec["total_sales"]
            kpi_total["net_sales"] += rec["net_sales"]
            kpi_total["total_point"] += rec["total_point"]
            kpi_total["total_fee"] += rec["total_fee"]

        # ── 추가: by_category / by_product ───────────────
        dfs = [df for df in [offline, online]
               if df is not None and not df.empty]
        if dfs:
            combined = pd.concat(dfs, ignore_index=True)
            kpi_summary["by_category"] = _compute_by_category(combined)
            kpi_summary["by_product"] = _compute_by_product(combined, top_n=20)
            logger.info(
                f"카테고리 집계: {len(kpi_summary['by_category'])}개 소분류 / "
                f"제품 집계: {len(kpi_summary['by_product'])}개"
            )

        logger.info(
            f"KPI 집계 완료: {len(by_platform)}개 플랫폼, "
            f"총매출 {kpi_total['total_sales']:,}원"
        )

    except Exception as e:
        logger.warning(f"KPI 집계 실패: {e}")
        errors.append(f"KPI 집계 실패: {e}")

    return {**state, "kpi_summary": kpi_summary, "kpi_total": kpi_total, "errors": errors}