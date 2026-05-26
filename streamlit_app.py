import streamlit as st
from db import init_db

st.set_page_config(
    page_title="SalesCoach",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()
st.switch_page("pages/1_upload.py")
