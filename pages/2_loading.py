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

progress_bar = st.progress(0, text="파이프라인 시작...")

STEP_LABELS = [
    ("📂", "파일 로드"),
    ("🔧", "데이터 전처리"),
    ("📈", "KPI 집계"),
    ("💾", "DB 저장"),
    ("📊", "월 누계 조회"),
    ("🎯", "타겟 달성률 계산"),
    ("🔍", "이상치 탐지"),
    ("🤖", "AI 코멘터리 생성"),
    ("📄", "리포트 생성"),
    ("📧", "이메일 발송"),
]

STEPS = [
    (10, "파일 로드"),
    (20, "데이터 전처리"),
    (35, "KPI 집계"),
    (48, "DB 저장"),
    (55, "월 누계 조회"),
    (65, "타겟 달성률 계산"),
    (75, "이상치 탐지"),
    (85, "AI 코멘터리 생성"),
    (93, "리포트 생성"),
    (99, "이메일 발송 처리"),
]


def render_steps(current_idx: int) -> str:
    html = '<div style="max-width:480px; margin:24px auto;">'
    for i, (icon, label) in enumerate(STEP_LABELS):
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


steps_placeholder = st.empty()

try:
    from graph import build_graph
    import threading

    config = st.session_state["run_config"]
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
        if step_idx < len(STEPS):
            pct, label = STEPS[step_idx]
            progress_bar.progress(pct, text=f"{label} 처리 중...")
            steps_placeholder.markdown(render_steps(step_idx), unsafe_allow_html=True)
            step_idx += 1
        time.sleep(0.8)

    thread.join()

    if "error" in error_container:
        raise error_container["error"]

    result_state = result_container.get("state")
    steps_placeholder.markdown(render_steps(len(STEPS)), unsafe_allow_html=True)
    progress_bar.progress(100, text="완료!")

    st.session_state["result_state"] = result_state
    st.switch_page("pages/3_report.py")

except Exception as e:
    st.error(f"파이프라인 실행 중 오류가 발생했습니다: {e}")
    logging.exception(e)
    st.page_link("pages/1_upload.py", label="← 처음부터 다시 시작")
