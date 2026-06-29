import logging
import time

import streamlit as st
from dotenv import load_dotenv

from utils.styles import inject_global_css, render_sidebar_brand

load_dotenv()

st.set_page_config(page_title="SalesCoach — 분석 중", page_icon="⏳", layout="wide")

inject_global_css()
render_sidebar_brand()

if "run_config" not in st.session_state:
    st.warning("업로드 페이지에서 파일을 먼저 업로드하세요.")
    st.page_link("pages/1_upload.py", label="← 업로드 페이지로 이동")
    st.stop()

st.markdown("""
<div style="margin-bottom:20px;">
  <div style="font-size:20px; font-weight:700; color:#e2e8f0;">⏳ 리포트 생성 중</div>
  <div style="font-size:13px; color:#718096; margin-top:3px;">파이프라인이 실행되는 동안 잠시 기다려 주세요.</div>
</div>
""", unsafe_allow_html=True)


def build_steps(output_options: list, has_recipients: bool) -> list:
    """선택된 옵션에 따라 표시할 단계 목록 구성. (icon, label, pct) 튜플 리스트."""
    steps = [
        ("📂", "파일 로드", 10),
        ("🔧", "데이터 전처리", 20),
        ("📈", "KPI 집계", 35),
        ("💾", "DB 저장", 48),
        ("📊", "월 누계 조회", 55),
        ("🎯", "타겟 달성률 계산", 65),
        ("🔍", "이상치 탐지", 75),
        ("🤖", "AI 코멘터리 생성", 85),
    ]

    if "html" in output_options and "excel" in output_options:
        steps.append(("📄", "리포트 생성 (HTML+Excel)", 93))
    elif "html" in output_options:
        steps.append(("📄", "HTML 리포트 생성", 93))
    elif "excel" in output_options:
        steps.append(("📄", "Excel 리포트 생성", 93))
    else:
        steps.append(("📄", "리포트 생성", 93))

    if has_recipients:
        steps.append(("📧", "이메일 발송", 99))

    return steps


def render_steps(current_idx: int, steps: list) -> str:
    html = '<div style="max-width:480px; margin:24px auto;">'
    for i, (icon, label, _pct) in enumerate(steps):
        if i < current_idx:
            color = "#10b981"
            status = "✅"
        elif i == current_idx:
            color = "#3b82f6"
            status = "⏳"
        else:
            color = "#2d3748"
            status = "○"
        weight = "600" if i == current_idx else "400"
        html += (
            f'<div style="display:flex;align-items:center;gap:12px;'
            f'padding:9px 0;border-bottom:1px solid #1e1e2e;">'
            f'<span style="font-size:15px;width:20px;text-align:center;">{status}</span>'
            f'<span style="font-size:13px;color:{color};font-weight:{weight};">{icon} {label}</span>'
            f'</div>'
        )
    html += "</div>"
    return html


config = st.session_state["run_config"]
output_options = config.get("output_options", [])
has_recipients = bool(config.get("recipient_emails", []))
current_steps = build_steps(output_options, has_recipients)

progress_bar = st.progress(0, text="파이프라인 시작...")
steps_placeholder = st.empty()

try:
    from graph import build_graph
    import threading

    app = build_graph()

    result_container = {}
    error_container = {}

    def run_pipeline():
        try:
            result_container["state"] = app.invoke(config)
        except Exception as e:
            error_container["error"] = e

    thread = threading.Thread(target=run_pipeline, daemon=True)
    thread.start()

    step_idx = 0
    while thread.is_alive():
        if step_idx < len(current_steps):
            icon, label, pct = current_steps[step_idx]
            progress_bar.progress(pct, text=f"{label} 처리 중...")
            steps_placeholder.markdown(render_steps(step_idx, current_steps), unsafe_allow_html=True)
            step_idx += 1
        time.sleep(0.8)

    thread.join()

    if "error" in error_container:
        raise error_container["error"]

    result_state = result_container.get("state")
    steps_placeholder.markdown(render_steps(len(current_steps), current_steps), unsafe_allow_html=True)
    progress_bar.progress(100, text="완료!")

    st.session_state["result_state"] = result_state
    st.switch_page("pages/3_report.py")

except Exception as e:
    st.error(f"파이프라인 실행 중 오류가 발생했습니다: {e}")
    logging.exception(e)
    st.page_link("pages/1_upload.py", label="← 처음부터 다시 시작")
