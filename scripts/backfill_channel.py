#!/usr/bin/env python3
"""daily_kpi.channel 백필 — 일회성 실행 스크립트 (Decision 33).

배경: channel 컬럼은 스키마에 있었지만 db_nodes.py/seed_db.py 둘 다
빈 문자열("")로 하드코딩 삽입해왔다. report_nodes.py/pattern_nodes.py/
insight_node.py의 매장이름 하드코딩을 channel 필드 참조로 교체하기 전에,
기존 행들의 channel을 지금까지 써온 매장이름 기준(OFFLINE_STORE_MAP 키)으로
1회 채워 넣는다. 이후 신규 삽입은 kpi_compute_node가 channel을 직접 태깅.

멱등: channel='' 인 행만 대상이므로 여러 번 실행해도 안전.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import get_db
from config import OFFLINE_STORE_MAP

OFFLINE_PLATFORMS = tuple(OFFLINE_STORE_MAP.keys())


def backfill():
    placeholders = ",".join("?" for _ in OFFLINE_PLATFORMS)
    with get_db() as conn:
        offline_n = conn.execute(
            f"UPDATE daily_kpi SET channel = '오프라인' "
            f"WHERE channel = '' AND platform IN ({placeholders})",
            OFFLINE_PLATFORMS,
        ).rowcount
        online_n = conn.execute(
            f"UPDATE daily_kpi SET channel = '온라인' "
            f"WHERE channel = '' AND platform NOT IN ({placeholders})",
            OFFLINE_PLATFORMS,
        ).rowcount
        conn.commit()
    print(f"백필 완료: 오프라인 {offline_n}건, 온라인 {online_n}건")


if __name__ == "__main__":
    backfill()
