import time

import streamlit as st

_KEY = "_report_gen_times"
LIMIT = 5
WINDOW_SECONDS = 3600


def check_and_record_report_generation() -> bool:
    """세션당 리포트 생성 속도제한. 최근 1시간 내 LIMIT건을 넘으면 False —
    이 경우 타임스탬프를 기록하지 않고(시도 자체를 카운트에 안 넣음) 거부."""
    now = time.time()
    times = [t for t in st.session_state.get(_KEY, []) if now - t < WINDOW_SECONDS]
    st.session_state[_KEY] = times

    if len(times) >= LIMIT:
        return False

    times.append(now)
    st.session_state[_KEY] = times
    return True
