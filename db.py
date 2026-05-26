import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "salescoach.db"


def get_db() -> sqlite3.Connection:
    return sqlite3.connect(str(DB_PATH), check_same_thread=False)


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_kpi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_date TEXT NOT NULL,
                channel TEXT NOT NULL DEFAULT '',
                platform TEXT NOT NULL,
                zor INTEGER,
                zre INTEGER,
                net_receipt INTEGER,
                hcc_revenue REAL,
                helinox_revenue REAL,
                total_revenue REAL,
                total_point REAL,
                total_fee REAL,
                created_at TEXT,
                UNIQUE(report_date, channel, platform)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS monthly_target (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year_month TEXT NOT NULL,
                platform TEXT NOT NULL,
                target REAL,
                UNIQUE(year_month, platform)
            )
        """)
        conn.commit()
    logger.info("DB 초기화 완료")
