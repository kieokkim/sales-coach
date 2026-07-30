import os

import streamlit as st

from utils.env import is_demo_mode

_SESSION_KEY = "_authenticated"


def require_password() -> bool:
    """비밀번호 게이트. DEMO_MODE면 통과. APP_PASSWORD 미설정 시 안전한 쪽
    (막는 쪽)으로 동작. 통과 못하면 False — 호출부에서 st.stop() 처리."""
    if is_demo_mode():
        return True

    app_password = os.getenv("APP_PASSWORD", "")
    if not app_password:
        st.error(
            "이 앱은 비밀번호로 보호되어야 하는데 APP_PASSWORD가 설정되지 "
            "않았습니다. 관리자에게 문의하세요."
        )
        return False

    if st.session_state.get(_SESSION_KEY):
        return True

    pw = st.text_input("비밀번호", type="password", key="_pw_input")
    if pw:
        if pw == app_password:
            st.session_state[_SESSION_KEY] = True
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    return False
