"""리포트 페이지 순수 표시 스타일 헬퍼 — 판단 로직 아님, nodes/에 안 둠.

utils/styles.py(전역 사이드바/앱 크롬)와 나란히 두는 이유는 같은 성격의
'표시 전용' 헬퍼이기 때문. 이 모듈은 pages/3_report.py에서만 쓴다.
"""

# 지역 키워드 → 브랜드 색상. 매장이름(HCC/HCC Store 1 등) 하드코딩이 아니라
# 판매처명 문자열에 이 키워드가 포함되는지로 판별한다(Decision 33 후속).
# 현재 합성 샘플 데이터("HCC", "HCC Store 1"...)엔 이 키워드가 안 들어있어
# 전부 중립회색으로 뜨는 게 정상 — 실제 헬리녹스 export 파일의 판매처명에
# 지역명이 포함될 때부터 색이 실제로 갈린다.
_REGION_COLOR = [
    ("서울", "#E23F8C"),  # pink
    ("부산", "#2E9BE6"),  # blue
    ("제주", "#F0932B"),  # orange
    ("여주", "#C7D92B"),  # yellow
]
NEUTRAL_GRAY = "#8C8C8C"


def get_store_color(platform_name: str) -> str:
    name = platform_name or ""
    for keyword, color in _REGION_COLOR:
        if keyword in name:
            return color
    return NEUTRAL_GRAY


# 라이트/다크 토글 — 목업 salescoach_mockup_v2.html의 :root / body[data-theme=light] 값 그대로.
# 사이드바·탭·expander 등 Streamlit 네이티브 크롬은 계속 다크 고정(범위 밖) —
# 여기 값은 페이지가 직접 그리는 HTML 블록(KPI스트립/카드/차트)에만 인라인으로 꽂는다.
THEMES = {
    "dark": {
        "bg": "#0E0E0E", "surface": "#1A1A1A", "surface_raised": "#242424", "line": "#333333",
        "text_primary": "#F2F2F2", "text_secondary": "#A3A3A3", "text_tertiary": "#6E6E6E",
        "danger": "#C0392B", "danger_soft": "#2E1815",
        "success": "#3F9D57", "success_soft": "#152A19",
        "accent": "#2E9BE6", "accent_soft": "#132433",
        "gray_1": "#8C8C8C", "gray_2": "#6E6E6E", "gray_3": "#525252",
    },
    "light": {
        "bg": "#FFFFFF", "surface": "#F7F7F7", "surface_raised": "#EFEFEF", "line": "#E0E0E0",
        "text_primary": "#141414", "text_secondary": "#5C5C5C", "text_tertiary": "#8C8C8C",
        "danger": "#C0392B", "danger_soft": "#FBEAE8",
        "success": "#3F9D57", "success_soft": "#E7F4EA",
        "accent": "#2E9BE6", "accent_soft": "#E7F2FC",
        "gray_1": "#C2C2C2", "gray_2": "#A0A0A0", "gray_3": "#7C7C7C",
    },
}


def get_theme(name: str) -> dict:
    return THEMES.get(name, THEMES["dark"])
