import streamlit as st
from db import init_db
from utils.auth import require_password
from utils.demo import ensure_demo_data
from utils.env import is_demo_mode

st.set_page_config(
    page_title="SalesCoach",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

if not require_password():
    st.stop()

init_db()
if is_demo_mode():
    ensure_demo_data()
st.switch_page("pages/1_upload.py")
