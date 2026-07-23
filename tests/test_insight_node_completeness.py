"""
완전성게이트(_enforce_completeness) API키 조기return 우회 수정 회귀테스트
(Decision 32 item8-A 재현 케이스).

세 케이스 모두 GT(ground_truth)가 "목표미달"을 확정하는 합성 state를 넣고,
insight_node 실행 후 top_issues에 "목표미달" 카테고리가 반드시 들어가는지
(=완전성 게이트가 실제로 실행됐는지)를 확인한다.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _make_state():
    return {
        "report_date": "20990101",  # anchor_set에 없는 날짜 — rule GT 경로 사용
        "patterns": {
            "adjusted_daily_target": {
                "severity": "high",
                "achievement_vs_adjusted": 40.0,
                "today_net_sales": 1000,
                "adjusted_daily_required": 2500,
                "days_remaining": 10,
                "adjustments_applied": [],
            },
            "return_anomalies": [],
            "discount_sensitivity": {},
            "trend_direction_30d": {},
            "category_movers": [],
        },
        "kpi_summary": {"by_product": []},
        "errors": [],
    }


def test_api_key_missing_gate_still_runs(monkeypatch):
    """케이스1: API키 자체 없음 — 이전엔 완전성게이트가 아예 안 돌아 top_issues=None."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from nodes.insight_node import insight_node

    result = insight_node(_make_state())
    top_issues = result["insights"].get("top_issues")

    assert isinstance(top_issues, list), "top_issues가 리스트여야 함(완전성 게이트 실행 증거)"
    categories = {it.get("category") for it in top_issues}
    assert "목표미달" in categories, "GT가 확정한 목표미달이 fallback으로 채워져야 함"
    assert any("OPENAI_API_KEY" in e for e in result["errors"]), (
        "errors에 API키 미설정 안내 문구가 있어야 함 (3_report.py 경고 expander 노출용)"
    )


def test_llm_call_exception_gate_still_runs(monkeypatch):
    """케이스2: API키는 있으나 호출 도중 예외(네트워크 오류 등) — 회귀 확인."""
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key-for-test")

    import langchain_openai

    class _FakeChatOpenAI:
        def __init__(self, *a, **k):
            pass

        def invoke(self, *a, **k):
            raise ConnectionError("simulated network failure")

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", _FakeChatOpenAI)

    from nodes.insight_node import insight_node

    result = insight_node(_make_state())
    top_issues = result["insights"].get("top_issues")

    assert isinstance(top_issues, list)
    categories = {it.get("category") for it in top_issues}
    assert "목표미달" in categories
    assert any("insight_node 실패" in e for e in result["errors"])


def test_normal_llm_success_path_unaffected(monkeypatch):
    """케이스3: 정상 케이스 — LLM 호출 성공 시 기존 동작(카테고리게이트+완전성게이트) 그대로."""
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key-for-test")

    import langchain_openai

    class _FakeResponse:
        content = (
            '{"top_issues": [{"issue": "테스트 목표미달 서술", "category": "목표미달"}], '
            '"relation": null, "forecast_summary": "", "trend_summary": "", '
            '"promo_insight": null, "risk_items": [], "opportunity_items": []}'
        )

    class _FakeChatOpenAI:
        def __init__(self, *a, **k):
            pass

        def invoke(self, *a, **k):
            return _FakeResponse()

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", _FakeChatOpenAI)

    from nodes.insight_node import insight_node

    result = insight_node(_make_state())
    top_issues = result["insights"].get("top_issues")

    assert isinstance(top_issues, list)
    categories = {it.get("category") for it in top_issues}
    assert "목표미달" in categories
    # 정상 경로는 insight_node 실패 로그가 없어야 함
    assert not any("insight_node 실패" in e for e in result["errors"])


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
