"""qa_nodes SQL 생성 정확도 테스트 — schema context + sql_guard 검증"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nodes.qa_nodes import get_schema_context, sql_guard


def test_schema_has_aggregation_rules():
    schema = get_schema_context()
    assert "SUM()" in schema, "SUM() 집계 규칙 누락"
    assert "여러 행" in schema, "다중 행 경고 누락"


def test_schema_product_table_guidance():
    schema = get_schema_context()
    assert "V.TARP" in schema, "제품명 예시(V.TARP) 누락"
    assert "daily_product" in schema, "daily_product 테이블 안내 누락"


def test_schema_zre_qty_column_name():
    schema = get_schema_context()
    assert "zre_qty" in schema, "zre_qty 컬럼명 안내 누락"


def test_schema_like_pattern_guidance():
    schema = get_schema_context()
    assert "LIKE" in schema, "LIKE 부분일치 검색 안내 누락"


def test_guard_blocks_delete():
    ok, msg = sql_guard("DELETE FROM daily_kpi")
    assert not ok
    assert "SELECT" in msg


def test_guard_blocks_drop():
    ok, msg = sql_guard("DROP TABLE daily_kpi")
    assert not ok


def test_guard_blocks_insert():
    ok, msg = sql_guard("INSERT INTO daily_kpi VALUES (1)")
    assert not ok


def test_guard_allows_select_with_sum():
    sql = "SELECT SUM(total_revenue) as total FROM daily_kpi WHERE report_date = '2026-06-05'"
    ok, cleaned = sql_guard(sql)
    assert ok
    assert "SUM" in cleaned


def test_guard_allows_product_query():
    sql = "SELECT SUM(zre_qty) FROM daily_product WHERE product_name LIKE '%V.TARP%'"
    ok, cleaned = sql_guard(sql)
    assert ok
    assert "daily_product" in cleaned.lower() or "DAILY_PRODUCT" in cleaned


def test_guard_blocks_disallowed_table():
    ok, msg = sql_guard("SELECT * FROM users")
    assert not ok
    assert "허용되지 않은 테이블" in msg


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
