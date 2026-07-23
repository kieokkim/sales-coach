"""generate_answer() SUM/AVG 집계 None행 가드 회귀테스트 (CLAUDE.md 다음과제 item3).

배경: SUM/AVG 집계쿼리는 매칭 행이 0건이어도 컬럼값이 None인 행 1개를
반환한다(빈 리스트 아님). COUNT는 매칭 0건이면 0을 반환하지 None이 아니다.
기존 `if not rows` 가드는 빈 리스트만 잡아 이 케이스를 놓치고 LLM 호출까지
넘어갔다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _make_fake_chatopenai(monkeypatch, call_counter, content="더미 응답"):
    import langchain_openai

    class _FakeResponse:
        pass

    class _FakeChatOpenAI:
        def __init__(self, *a, **k):
            pass

        def invoke(self, *a, **k):
            call_counter.append(1)
            resp = _FakeResponse()
            resp.content = content
            return resp

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", _FakeChatOpenAI)


def test_sum_query_no_match_returns_guidance_without_llm_call(monkeypatch):
    """케이스1: SUM 쿼리 매칭 0건 (None값 행 1개) — 안내메시지, LLM 호출 없음."""
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key-for-test")
    calls = []
    _make_fake_chatopenai(monkeypatch, calls)

    from nodes.qa_nodes import generate_answer

    rows = [{"total_revenue": None}]
    answer = generate_answer("존재하지 않는 날짜의 매출은?", "SELECT SUM(total_revenue) ...", rows)

    assert answer == "조회된 데이터가 없습니다."
    assert len(calls) == 0, "None 집계행에서 LLM이 호출되면 안 됨"


def test_sum_query_with_match_calls_llm_normally(monkeypatch):
    """케이스2: SUM 쿼리 매칭 있음 — 정상 값, LLM 정상 호출."""
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key-for-test")
    calls = []
    _make_fake_chatopenai(monkeypatch, calls, content="총 매출은 100만원입니다.")

    from nodes.qa_nodes import generate_answer

    rows = [{"total_revenue": 1000000}]
    answer = generate_answer("오늘 전체 매출 얼마야?", "SELECT SUM(total_revenue) ...", rows)

    assert answer == "총 매출은 100만원입니다."
    assert len(calls) == 1, "정상 매칭 케이스는 LLM이 1회 호출돼야 함"


def test_empty_rows_regression_unaffected(monkeypatch):
    """케이스3: 기존 빈 리스트(비집계 쿼리, 매칭없음) — 회귀 없이 그대로."""
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key-for-test")
    calls = []
    _make_fake_chatopenai(monkeypatch, calls)

    from nodes.qa_nodes import generate_answer

    answer = generate_answer("V.TARP 재고는?", "SELECT * FROM daily_product WHERE ...", [])

    assert answer == "조회된 데이터가 없습니다."
    assert len(calls) == 0


def test_sum_with_count_star_no_match_still_caught(monkeypatch):
    """케이스4: SUM + COUNT(*) 병행 쿼리, 매칭 0건 — COUNT는 0(None 아님)이지만
    SUM 컬럼이 None이라 any-None 기준으로 여전히 가드에 걸려야 함."""
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key-for-test")
    calls = []
    _make_fake_chatopenai(monkeypatch, calls)

    from nodes.qa_nodes import generate_answer

    rows = [{"total_qty": None, "cnt": 0}]
    answer = generate_answer(
        "존재하지 않는 제품의 판매건수와 수량은?",
        "SELECT SUM(qty) as total_qty, COUNT(*) as cnt ...",
        rows,
    )

    assert answer == "조회된 데이터가 없습니다."
    assert len(calls) == 0


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
