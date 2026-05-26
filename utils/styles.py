import streamlit as st


def inject_global_css():
    st.markdown("""
    <style>
    #MainMenu {visibility:hidden;}
    footer {visibility:hidden;}
    header {visibility:hidden;}
    .stApp {background:#0f0f1a;}
    [data-testid="stSidebar"] {
        background:#0a0a14;
        border-right:1px solid #1e1e2e;
    }
    [data-testid="stSidebarNavLink"] {
        color:#718096 !important;
        font-size:13px !important;
        border-radius:6px !important;
    }
    [data-testid="stSidebarNavLink"][aria-current="page"] {
        background:#1e1e2e !important;
        color:#e2e8f0 !important;
    }
    h1, h2, h3, h4 {color:#e2e8f0 !important;}
    p, li, label, .stMarkdown {color:#cbd5e0;}
    .stProgress > div > div {background:#3b82f6;}
    .stAlert {border-radius:8px;}
    [data-testid="stMetric"] {background:#1e1e2e; border-radius:10px; padding:12px;}
    [data-testid="stMetricLabel"] {color:#718096 !important;}
    [data-testid="stMetricValue"] {color:#e2e8f0 !important;}
    .stTabs [data-baseweb="tab"] {color:#718096;}
    .stTabs [aria-selected="true"] {color:#e2e8f0 !important; border-bottom-color:#3b82f6 !important;}
    .stButton > button {border-radius:8px;}
    [data-testid="stForm"] {background:#1a1a2e; border-radius:12px; padding:16px; border:1px solid #1e1e2e;}
    [data-testid="stSidebarNav"] span { display: none; }
    [data-testid="stSidebarNavLink"] p { display: none; }
    </style>
    """, unsafe_allow_html=True)


def render_sidebar_brand():
    st.sidebar.markdown("""
    <div style="padding:16px 8px 20px; border-bottom:1px solid #1e1e2e; margin-bottom:8px;">
        <div style="font-size:17px; font-weight:700; color:#e2e8f0;">📊 SalesCoach</div>
        <div style="font-size:11px; color:#4a5568; margin-top:3px;">AI 매출 분석 에이전트</div>
    </div>
    """, unsafe_allow_html=True)
