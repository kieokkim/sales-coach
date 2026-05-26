import os
import tempfile
from datetime import date, timedelta

import streamlit as st
from dotenv import load_dotenv

from utils.styles import inject_global_css, render_sidebar_brand

load_dotenv()

st.set_page_config(page_title="SalesCoach — 파일 업로드", page_icon="📤", layout="wide")

inject_global_css()
render_sidebar_brand()

st.markdown("""
<div style="margin-bottom:24px;">
  <div style="font-size:22px; font-weight:700; color:#e2e8f0;">📊 SalesCoach</div>
  <div style="font-size:13px; color:#718096; margin-top:3px;">ERP 데이터로 판매일보를 자동 생성합니다.</div>
</div>
""", unsafe_allow_html=True)
st.divider()

col1, col2 = st.columns(2)

with col1:
    offline_file = st.file_uploader(
        "오프라인 거래 파일 (필수)",
        type=["xlsx", "xls"],
        help="ERP에서 다운로드한 오프라인 거래 Excel 파일",
    )

with col2:
    online_file = st.file_uploader(
        "온라인 거래 파일 (선택)",
        type=["xlsx", "xls"],
        help="ERP에서 다운로드한 온라인 거래 Excel 파일",
    )

st.divider()

col3, col4 = st.columns(2)

with col3:
    report_date = st.date_input(
        "리포트 기준일",
        value=date.today() - timedelta(days=1),
        help="분석 기준일을 선택하세요.",
    )

with col4:
    output_options_display = st.multiselect(
        "리포트 출력 형식",
        options=["📧 HTML 이메일", "📥 Excel 파일"],
        default=["📧 HTML 이메일", "📥 Excel 파일"],
    )

label_map = {"📧 HTML 이메일": "html", "📥 Excel 파일": "excel"}
output_options = [label_map[o] for o in output_options_display]

recipient_input = st.text_area(
    "수신자 이메일 (줄바꿈 또는 쉼표로 구분)",
    placeholder="example@company.com\nmanager@company.com",
    height=80,
)

with st.expander("⚙️ 타겟 설정 (선택)", expanded=False):
    st.caption("전체 월 타겟 금액을 설정합니다. 플랫폼별 타겟은 config.py에서 수정하세요.")
    monthly_target_input = st.number_input(
        f"{report_date.year}-{report_date.month:02d} 전체 타겟 매출 (원)",
        min_value=0,
        value=0,
        step=1_000_000,
        format="%d",
    )

st.divider()

run_btn = st.button(
    "🚀 리포트 생성",
    type="primary",
    disabled=(offline_file is None or not output_options),
    use_container_width=True,
)

if offline_file is None:
    st.info("오프라인 거래 파일을 업로드하면 리포트 생성이 활성화됩니다.")

if run_btn and offline_file is not None:
    offline_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    offline_tmp.write(offline_file.read())
    offline_tmp.flush()

    online_tmp_path = ""
    if online_file is not None:
        online_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
        online_tmp.write(online_file.read())
        online_tmp.flush()
        online_tmp_path = online_tmp.name

    recipients = [
        r.strip()
        for r in recipient_input.replace(",", "\n").splitlines()
        if r.strip()
    ]

    st.session_state["run_config"] = {
        "offline_path": offline_tmp.name,
        "online_path": online_tmp_path,
        "output_options": output_options,
        "recipient_emails": recipients,
        "report_date": report_date.strftime("%Y%m%d"),
        "monthly_target_override": monthly_target_input,
        "errors": [],
    }

    st.switch_page("pages/2_loading.py")
