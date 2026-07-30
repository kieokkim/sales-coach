from datetime import date

import streamlit as st
from dotenv import load_dotenv

from nodes.qa_nodes import answer_question
from utils.auth import require_password
from utils.demo import render_demo_banner
from utils.env import is_demo_mode
from utils.styles import inject_global_css, render_sidebar_brand

load_dotenv()

st.set_page_config(page_title="SalesCoach — 데이터 질의", page_icon="💬", layout="wide")

if not require_password():
    st.stop()

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

if is_demo_mode():
    render_demo_banner()
    st.warning("이 기능은 데모에서 비활성화되어 있습니다 (자유 입력이 LLM 호출로 "
               "직결되어 비용 보호 차원에서 막아둠).")
    st.markdown("""
**이 기능이 하는 일:**
- 사용자의 자연어 질문을 LLM이 SQL `SELECT` 쿼리로 변환해 저장된 매출
  데이터(`daily_kpi`/`daily_product`)를 조회합니다.
- **SELECT 전용 화이트리스트 가드**가 적용되어 있어, LLM이 실수로든
  의도적으로든 `INSERT`/`UPDATE`/`DELETE`/`DROP` 등 조회 이외의 쿼리를
  생성해도 실행 전 차단됩니다.
- 질문이 저장된 데이터로 답할 수 없는 종류(예: 미래 예측, 데이터에 없는
  항목)일 경우 LLM이 억지로 답을 지어내지 않고 "답변 불가"를 감지해
  명시적으로 알립니다.
""")
else:
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
