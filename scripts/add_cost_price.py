#!/usr/bin/env python3
"""product_master.xlsx에 원가(cost_price) 컬럼 추가 — 일회성 실행 스크립트"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

MARGIN_BY_CATEGORY = {
    "체어": 1.35,
    "테이블": 1.40,
    "텐트": 1.50,
}
FALLBACK_MARGIN = 1.40

MASTER_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "product_master.xlsx"
)


def main():
    df = pd.read_excel(MASTER_PATH)

    if "원가" in df.columns:
        print("원가 컬럼 이미 존재. 덮어씁니다.")

    df["margin_multiplier"] = df["중분류내역"].map(MARGIN_BY_CATEGORY).fillna(FALLBACK_MARGIN)
    df["원가"] = (df["단가"] / df["margin_multiplier"]).round().astype(int)
    df = df.drop(columns=["margin_multiplier"])

    df.to_excel(MASTER_PATH, index=False)

    print(df[["제품명", "중분류내역", "단가", "원가"]].head(10).to_string())
    print(f"\n총 {len(df)}개 제품 원가 추가 완료")

    print("\n[마진율 검증]")
    for cat, mult in sorted(MARGIN_BY_CATEGORY.items()):
        subset = df[df["중분류내역"] == cat]
        if not subset.empty:
            avg_ratio = (subset["단가"] / subset["원가"]).mean()
            print(f"  {cat}: 평균 단가/원가 = {avg_ratio:.3f} (기대: {mult:.3f})")
    others = df[~df["중분류내역"].isin(MARGIN_BY_CATEGORY)]
    if not others.empty:
        avg_ratio = (others["단가"] / others["원가"]).mean()
        print(f"  기타: 평균 단가/원가 = {avg_ratio:.3f} (기대: {FALLBACK_MARGIN:.3f})")


if __name__ == "__main__":
    main()
