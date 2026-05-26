import logging
import pandas as pd
from config import (
    CATEGORY_ALIAS,
    EXCLUDE_ORDER_TYPES,
    HELINOX_PRODUCT_KEYWORD,
    ONLINE_PLATFORM_MAP,
)

logger = logging.getLogger(__name__)


def _preprocess_offline(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    drop_cols = [c for c in ["상태", "납품요청일자"] if c in df.columns]
    df = df.drop(columns=drop_cols)

    # ZFD 및 null 오더유형 제거
    df = df[~df["오더유형"].isin(EXCLUDE_ORDER_TYPES)]
    df = df[df["오더유형"].notna()]

    # 대분류 정규화
    def normalize_category(row):
        cat = row.get("대분류내역", "")
        product = str(row.get("제품명", "") or "")
        if pd.isna(cat) or cat == "":
            if HELINOX_PRODUCT_KEYWORD in product:
                return "헬리녹스"
            return "HCC"
        return CATEGORY_ALIAS.get(cat, cat)

    df["대분류내역"] = df.apply(normalize_category, axis=1)

    # 봉사료 = 배송비 + 쇼핑백
    df["봉사료"] = df.get("배송비", 0).fillna(0) + df.get("쇼핑백", 0).fillna(0)

    # 판매일자: 고객 참조 번호 str[9:17]
    # 예: 'ORD00000120250525HCC' → str[9:17] = '20250525'
    df["판매일자"] = df["고객 참조 번호"].astype(str).str[9:17]

    # 매출 컬럼 통일
    if "S/O sum" in df.columns:
        df = df.rename(columns={"S/O sum": "매출", "S/O수량": "수량"})

    return df


def _preprocess_online(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    drop_cols = [c for c in ["상태", "납품요청일자"] if c in df.columns]
    df = df.drop(columns=drop_cols)

    df = df[~df["오더유형"].isin(EXCLUDE_ORDER_TYPES)]
    df = df[df["오더유형"].notna()]

    def normalize_category(row):
        cat = row.get("대분류내역", "")
        product = str(row.get("제품명", "") or "")
        if pd.isna(cat) or cat == "":
            if HELINOX_PRODUCT_KEYWORD in product:
                return "헬리녹스"
            return "HCC"
        return CATEGORY_ALIAS.get(cat, cat)

    df["대분류내역"] = df.apply(normalize_category, axis=1)

    df["봉사료"] = df.get("배송비", 0).fillna(0) + df.get("쇼핑백", 0).fillna(0)

    # 온라인: 판매일자 = 청구일 컬럼
    df["판매일자"] = df["청구일"].astype(str)

    # 판매처명 그룹핑
    df["판매처명"] = df["판매처명"].map(ONLINE_PLATFORM_MAP).fillna(df["판매처명"])

    # 매출 컬럼 통일
    if "총금액" in df.columns:
        df = df.rename(columns={"총금액": "매출", "청구수량": "수량"})

    return df


def preprocess_node(state: dict) -> dict:
    errors = list(state.get("errors", []))
    offline_processed = pd.DataFrame()
    online_processed = pd.DataFrame()

    offline_df = state.get("offline_df")
    if offline_df is not None and not offline_df.empty:
        try:
            offline_processed = _preprocess_offline(offline_df)
            logger.info(f"오프라인 전처리 완료: {len(offline_processed)}행")
        except Exception as e:
            logger.warning(f"오프라인 전처리 실패: {e}")
            errors.append(f"오프라인 전처리 실패: {e}")

    online_df = state.get("online_df")
    if online_df is not None and not online_df.empty:
        try:
            online_processed = _preprocess_online(online_df)
            logger.info(f"온라인 전처리 완료: {len(online_processed)}행")
        except Exception as e:
            logger.warning(f"온라인 전처리 실패: {e}")
            errors.append(f"온라인 전처리 실패: {e}")

    return {
        **state,
        "offline_processed": offline_processed,
        "online_processed": online_processed,
        "errors": errors,
    }
