from typing import Any
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, END

from nodes.load_nodes import file_load_node
from nodes.preprocess_nodes import preprocess_node
from nodes.kpi_nodes import kpi_compute_node
from nodes.db_nodes import db_save_node, db_load_cumulative_node
from nodes.target_nodes import target_compare_node
from nodes.anomaly_nodes import anomaly_detect_node
from nodes.pattern_nodes import pattern_detect_node
from nodes.insight_node import insight_node
from nodes.action_node import action_node
from nodes.commentary_nodes import commentary_node
from nodes.report_nodes import build_html_node, build_excel_node
from nodes.email_nodes import email_send_node

class SalesDailyState(TypedDict):
    # 인풋
    offline_path: str
    online_path: str
    output_options: list[str]
    recipient_emails: list[str]
    report_date: str
    no_data_for_date: bool

    # 중간 결과
    offline_df: Any
    online_df: Any
    offline_processed: Any
    online_processed: Any

    # KPI
    kpi_summary: dict
    kpi_total: dict

    # DB 누계
    db_saved_count: int
    db_skipped_count: int
    kpi_cumulative: dict

    # 타겟 달성률
    target_summary: dict

    # 이상치
    anomalies: list[dict]

    # 판단 레이어
    patterns: dict
    insights: dict
    actions: list

    # LLM
    llm_commentary: str

    # 아웃풋
    html_report: str
    excel_path: str
    email_sent: bool

    # 에러
    errors: list[str]


def _route_after_commentary(state: SalesDailyState) -> str:
    options = set(state.get("output_options", ["html", "excel"]))
    if options == {"excel"}:
        return "excel_only"
    return "html_first"


def _route_after_preprocess(state: SalesDailyState) -> str:
    if state.get("no_data_for_date"):
        # kpi_compute~commentary(LLM 3회 호출 포함) 전부 건너뛰고 리포트 생성으로 바로 이동
        return _route_after_commentary(state)
    return "has_data"


def _route_after_html(state: SalesDailyState) -> str:
    options = set(state.get("output_options", ["html", "excel"]))
    if "excel" in options:
        return "add_excel"
    return "send_email"


def build_graph():
    graph = StateGraph(SalesDailyState)

    graph.add_node("file_load", file_load_node)
    graph.add_node("preprocess", preprocess_node)
    graph.add_node("kpi_compute", kpi_compute_node)
    graph.add_node("db_save", db_save_node)
    graph.add_node("db_load_cumulative", db_load_cumulative_node)
    graph.add_node("target_compare", target_compare_node)
    graph.add_node("anomaly_detect", anomaly_detect_node)
    graph.add_node("pattern_detect", pattern_detect_node)
    graph.add_node("insight", insight_node)
    graph.add_node("action", action_node)
    graph.add_node("commentary", commentary_node)
    graph.add_node("build_html", build_html_node)
    graph.add_node("build_excel", build_excel_node)
    graph.add_node("email_send", email_send_node)

    graph.set_entry_point("file_load")
    graph.add_edge("file_load", "preprocess")

    # preprocess → no_data_for_date면 kpi_compute~commentary 전부 스킵, 바로 리포트 생성으로
    graph.add_conditional_edges(
        "preprocess",
        _route_after_preprocess,
        {"has_data": "kpi_compute", "html_first": "build_html", "excel_only": "build_excel"},
    )

    graph.add_edge("kpi_compute", "db_save")
    graph.add_edge("db_save", "db_load_cumulative")
    graph.add_edge("db_load_cumulative", "target_compare")
    graph.add_edge("target_compare", "anomaly_detect")
    graph.add_edge("anomaly_detect", "pattern_detect")
    graph.add_edge("pattern_detect", "insight")
    graph.add_edge("insight", "action")
    graph.add_edge("action", "commentary")

    # commentary → html_first or excel_only
    graph.add_conditional_edges(
        "commentary",
        _route_after_commentary,
        {"html_first": "build_html", "excel_only": "build_excel"},
    )

    # build_html → add_excel(both) or send_email(html_only)
    graph.add_conditional_edges(
        "build_html",
        _route_after_html,
        {"add_excel": "build_excel", "send_email": "email_send"},
    )

    # build_excel: both → email_send, excel_only → END
    graph.add_conditional_edges(
        "build_excel",
        lambda s: "send_email" if "html" in s.get("output_options", []) else "done",
        {"send_email": "email_send", "done": END},
    )

    graph.add_edge("email_send", END)

    return graph.compile()


if __name__ == "__main__":
    app = build_graph()
    print("그래프 빌드 성공")
    print(f"노드 수: {len(app.nodes)}")
