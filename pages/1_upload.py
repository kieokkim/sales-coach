import os
import tempfile
from datetime import date, timedelta

import pandas as pd
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

# 오프라인 판별: S/O sum(또는 S/O수량) 컬럼 — nodes/preprocess_nodes.py:59-60 기준.
# 온라인 판별: 총금액(또는 청구수량) 컬럼 — nodes/preprocess_nodes.py:103-104 기준.
OFFLINE_SIGNATURE_COLS = {"S/O sum", "S/O수량"}
ONLINE_SIGNATURE_COLS = {"총금액", "청구수량"}


def _detect_channel(columns: set) -> str | None:
    is_offline = bool(columns & OFFLINE_SIGNATURE_COLS)
    is_online = bool(columns & ONLINE_SIGNATURE_COLS)
    if is_offline and not is_online:
        return "오프라인"
    if is_online and not is_offline:
        return "온라인"
    return None  # 컬럼 시그니처가 없거나(미확인 양식) 둘 다 있음(모호) — 자동판별 불가


uploaded_files = st.file_uploader(
    "거래 파일 업로드 (여러 개 선택 가능)",
    type=["xlsx", "xls"],
    accept_multiple_files=True,
    help="오프라인/온라인 파일을 구분 없이 올리면 컬럼 구성을 보고 자동 분류합니다.",
)

offline_dfs, online_dfs, unrecognized = [], [], []
for f in uploaded_files or []:
    df = pd.read_excel(f)
    channel = _detect_channel(set(df.columns))
    if channel == "오프라인":
        offline_dfs.append(df)
    elif channel == "온라인":
        online_dfs.append(df)
    else:
        unrecognized.append((f.name, list(df.columns)))

if unrecognized:
    for fname, cols in unrecognized:
        st.error(
            f"'{fname}' 파일의 채널을 자동판별하지 못했습니다. "
            f"오프라인 기준 컬럼({'/'.join(OFFLINE_SIGNATURE_COLS)}) 또는 "
            f"온라인 기준 컬럼({'/'.join(ONLINE_SIGNATURE_COLS)}) 중 "
            f"정확히 하나만 있어야 합니다. 감지된 컬럼: {cols}"
        )

offline_ready = bool(offline_dfs) and not unrecognized
if offline_dfs:
    st.caption(f"오프라인으로 분류됨: {len(offline_dfs)}개 파일")
if online_dfs:
    st.caption(f"온라인으로 분류됨: {len(online_dfs)}개 파일")

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

st.divider()

run_btn = st.button(
    "🚀 리포트 생성",
    type="primary",
    disabled=(not offline_ready or not output_options),
    use_container_width=True,
)

if not uploaded_files:
    st.info("오프라인 거래 파일을 최소 1개 업로드하면 리포트 생성이 활성화됩니다.")
elif not offline_dfs and not unrecognized:
    st.info("오프라인 거래 파일이 없습니다. 최소 1개 필요합니다(온라인은 선택).")

if run_btn and offline_ready:
    offline_combined = pd.concat(offline_dfs, ignore_index=True)
    offline_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    offline_combined.to_excel(offline_tmp.name, index=False)

    online_tmp_path = ""
    if online_dfs:
        online_combined = pd.concat(online_dfs, ignore_index=True)
        online_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
        online_combined.to_excel(online_tmp.name, index=False)
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
        "errors": [],
    }

    st.switch_page("pages/2_loading.py")
