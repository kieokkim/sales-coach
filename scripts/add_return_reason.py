#!/usr/bin/env python3
"""샘플 데이터에 오더사유명 합성 컬럼 추가 — 일회성 실행 스크립트.

ZOR 행은 공백("")으로 채움(실제 SAP 패턴과 동일).
ZRE 행은 실측 반품 내부 비중 근사치로 4개 사유 배정, seed(42)로 재현 가능.
각 파일마다 ZRE 1건은 매핑에 없는 "반품-기타사유"로 남겨 폴백 경로 검증용.
"""
import os

import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
FILES = [
    "sample_offline.xlsx",
    "sample_offline_3months.xlsx",
    "sample_online.xlsx",
    "sample_online_3months.xlsx",
]

REASONS = ["빠른 반품", "반품-변심", "반품-교환", "반품-불량"]
WEIGHTS = [0.60, 0.28, 0.10, 0.02]
UNMAPPED_FALLBACK = "반품-기타사유"


def main():
    for fname in FILES:
        path = os.path.join(DATA_DIR, fname)
        df = pd.read_excel(path)

        if "오더사유명" in df.columns:
            print(f"{fname}: 오더사유명 컬럼 이미 존재. 덮어씁니다.")

        np.random.seed(42)

        df["오더사유명"] = ""
        zre_mask = df["오더유형"] == "ZRE"
        n_zre = int(zre_mask.sum())
        if n_zre > 0:
            assigned = np.random.choice(REASONS, size=n_zre, p=WEIGHTS)
            df.loc[zre_mask, "오더사유명"] = assigned
            # 폴백 경로 검증용: ZRE 첫 행 하나는 매핑에 없는 값으로 강제 override
            first_zre_idx = df.index[zre_mask][0]
            df.loc[first_zre_idx, "오더사유명"] = UNMAPPED_FALLBACK

        df.to_excel(path, index=False)

        dist = df.loc[zre_mask, "오더사유명"].value_counts()
        print(f"{fname}: ZRE {n_zre}건 사유 분포\n{dist.to_string()}\n")


if __name__ == "__main__":
    main()
