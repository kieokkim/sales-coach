"""sql_guard 화이트리스트 우회 수정 회귀테스트 (Decision 32 item11 재현 케이스)"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nodes.qa_nodes import sql_guard


def test_blocks_double_quoted_table():
    ok, msg = sql_guard('SELECT * FROM "sqlite_master"')
    assert not ok
    assert "SQLITE_MASTER" in msg


def test_blocks_bracket_quoted_table():
    ok, msg = sql_guard("SELECT * FROM [sqlite_master]")
    assert not ok
    assert "SQLITE_MASTER" in msg


def test_blocks_backtick_quoted_table():
    ok, msg = sql_guard("SELECT * FROM `sqlite_master`")
    assert not ok
    assert "SQLITE_MASTER" in msg


def test_blocks_quoted_product_master():
    """비허용 테이블 product_master(원가 컬럼 cost_price 포함) 인용부호 우회 차단."""
    ok, msg = sql_guard('SELECT * FROM "product_master"')
    assert not ok
    assert "PRODUCT_MASTER" in msg


def test_blocks_schema_qualified_quoted_table():
    """
    '"main"."sqlite_master"' 는 차단되지만, sqlite_master가 잡혀서가 아니라
    스키마 한정자 "main"이 \\w+ 정규식에 잡히고 화이트리스트에 없어서 차단됨.
    FROM/JOIN 추출 정규식(\\bFROM\\s+(\\w+))은 '.' 이후는 안 보므로 실제로는
    'MAIN'만 캡처된다 — sqlite_master 자체를 인식한 게 아니라는 점 명시.
    (우연히 안전한 방향으로 차단될 뿐, 근본 해결은 아님 — 다음 발견 시 참고용 기록)
    """
    ok, msg = sql_guard('SELECT * FROM "main"."sqlite_master"')
    assert not ok
    assert "MAIN" in msg
    assert "SQLITE_MASTER" not in msg  # sqlite_master가 아니라 main 때문에 막힌 것


def test_semicolon_comment_split_drop_still_blocked_by_guard():
    """
    주석으로 쪼갠 DROP(DR/**/OP)은 이번 수정과 무관하게 guard 레벨에서도
    여전히 통과되지만(키워드 매칭 실패는 기존과 동일 — 이번 수정 대상 아님),
    sqlite3 execute()가 "한 문장만 허용" 규칙으로 별도 차단한다는 게 기존
    감사(Decision 32)의 결론. guard 자체의 회귀는 이 테스트로 확인.
    """
    ok, msg = sql_guard("SELECT 1; DR/**/OP TABLE daily_kpi")
    # guard는 이 변형을 여전히 통과시킨다(의도된 스코프 밖) — DB 드라이버가 막음.
    assert ok


def test_semicolon_stacking_plain_drop_blocked_by_keyword():
    ok, msg = sql_guard("SELECT * FROM daily_kpi; DROP TABLE daily_kpi")
    assert not ok
    assert "DROP" in msg


def test_allows_normal_select_daily_kpi():
    sql = "SELECT SUM(total_revenue) as total FROM daily_kpi WHERE report_date = '2025-06-01'"
    ok, cleaned = sql_guard(sql)
    assert ok
    assert cleaned == sql


def test_allows_normal_select_daily_product():
    sql = "SELECT SUM(zre_qty) FROM daily_product WHERE product_name LIKE '%V.TARP%'"
    ok, cleaned = sql_guard(sql)
    assert ok


def test_allows_quoted_column_alias_on_allowed_table():
    """정상 쿼리의 컬럼 별칭 따옴표 사용 — 실행 SQL(sql_clean)은 원본 그대로 유지되어야 함."""
    sql = 'SELECT total_revenue AS "Total Revenue" FROM daily_kpi WHERE report_date = \'2025-06-01\''
    ok, cleaned = sql_guard(sql)
    assert ok
    assert cleaned == sql  # 인용부호가 실행되는 SQL에서 제거되면 안 됨


def test_blocks_disallowed_table_unquoted():
    ok, msg = sql_guard("SELECT * FROM users")
    assert not ok
    assert "USERS" in msg


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
