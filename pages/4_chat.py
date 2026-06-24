from datetime import date

import streamlit as st
from dotenv import load_dotenv

from nodes.qa_nodes import answer_question
from utils.styles import inject_global_css, render_sidebar_brand

load_dotenv()

st.set_page_config(page_title="SalesCoach — 데이터 질의", page_icon="💬", layout="wide")

inject_global_css()
render_sidebar_brand()

st.markdown("""
<div style="margin-bottom:20px;">
  <div style="font-size:20px; font-weight:700; color:#e2e8f0;">💬 데이터에게 물어보기</div>
  <div style="font-size:13px; color:#718096; margin-top:3px;">
    저장된 매출 데이터에 자연어로 질문하세요. 예: "이번달 목표 달성 가능해?"
  </div>
</div>
""", unsafe_allow_html=True)

query_date = st.date_input("기준일 (질문에서 '오늘', '이번달' 기준)", value=date.today())
report_date_str = query_date.strftime("%Y-%m-%d")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg["role"] == "assistant" and msg.get("sql"):
            with st.expander("생성된 SQL 보기"):
                st.code(msg["sql"], language="sql")

if prompt := st.chat_input("질문을 입력하세요"):
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("데이터 조회 중..."):
            result = answer_question(prompt, report_date_str)

        if result["error"]:
            st.error(result["error"])
            answer_text = f"오류: {result['error']}"
        else:
            st.write(result["answer"])
            if result["sql"]:
                with st.expander("생성된 SQL 보기"):
                    st.code(result["sql"], language="sql")
            answer_text = result["answer"]

    st.session_state.chat_history.append({
        "role": "assistant",
        "content": answer_text,
        "sql": result.get("sql", ""),
    })

if st.session_state.chat_history:
    if st.button("대화 초기화"):
        st.session_state.chat_history = []
        st.rerun()
