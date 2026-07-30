import logging

import streamlit as st

from db import get_db

logger = logging.getLogger(__name__)


def ensure_demo_data() -> None:
    """DEMO_MODE 부팅 시 1회 호출. daily_kpi가 비어 있으면 합성 91일 데이터를
    자동 적재(scripts/seed_db.seed()는 멱등 — 이미 있으면 건드리지 않음)."""
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM daily_kpi").fetchone()[0]
    if count > 0:
        return

    logger.info("DEMO_MODE: daily_kpi 비어 있음 — 합성 데이터 자동 시딩 시작")
    from scripts.seed_db import seed
    seed()
    logger.info("DEMO_MODE: 합성 데이터 시딩 완료")


def render_demo_banner() -> None:
    st.info(
        "🧪 이 화면은 **합성 샘플 데이터**로 동작하는 데모입니다. "
        "실제 매장 데이터가 아니며, 실사용 파일럿은 별도 환경에서 운영됩니다.",
        icon="🧪",
    )
