import html
from calendar import monthrange
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
from dotenv import load_dotenv

from config import LLM_MODEL
from utils.styles import inject_global_css, render_sidebar_brand
from utils.ui_style import get_store_color, get_theme

load_dotenv()

st.set_page_config(page_title="SalesCoach — 리포트", page_icon="📊", layout="wide")

inject_global_css()
render_sidebar_brand()

if "result_state" not in st.session_state:
    st.warning("리포트 결과가 없습니다. 파일을 먼저 업로드하세요.")
    st.page_link("pages/1_upload.py", label="← 업로드 페이지로 이동")
    st.stop()

state = st.session_state["result_state"]
output_options = state.get("output_options", ["html", "excel"])
report_date_raw = state.get("report_date", "")
report_date_display = (
    f"{report_date_raw[:4]}-{report_date_raw[4:6]}-{report_date_raw[6:8]}"
    if len(report_date_raw) >= 8
    else report_date_raw
)

kpi_total = state.get("kpi_total", {})
kpi_cumulative = state.get("kpi_cumulative", {})
kpi_summary = state.get("kpi_summary", {})
target_summary = state.get("target_summary", {})
patterns = state.get("patterns", {})
insights = state.get("insights", {})
actions = state.get("actions", [])
anomalies = state.get("anomalies", [])
db_skipped_count = state.get("db_skipped_count", 0)
by_platform = kpi_summary.get("by_platform", [])


def esc(v) -> str:
    """LLM 산출 텍스트 전용 이스케이프. rule 계산값/수치엔 안 씀."""
    return html.escape(str(v)) if v else ""


if "report_theme" not in st.session_state:
    st.session_state["report_theme"] = "dark"
T = get_theme(st.session_state["report_theme"])


def _gray_ramp(theme: dict, n: int) -> list:
    """지역 키워드 무매칭으로 get_store_color가 전부 동일 회색일 때 파이차트용 대체.
    text_tertiary~text_primary 사이(둘 다 각 테마에서 이미 배경과 대비되는 무채색)를
    n개로 등분해 개수와 무관하게 겹치지 않는 회색조를 만든다."""
    def _to_rgb(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    c1, c2 = _to_rgb(theme["text_tertiary"]), _to_rgb(theme["text_primary"])
    if n <= 1:
        return [theme["text_tertiary"]]
    return [
        "#%02X%02X%02X" % tuple(round(c1[i] + (c2[i] - c1[i]) * k / (n - 1)) for i in range(3))
        for k in range(n)
    ]


def _prepare_time_series(offline_df, online_df):
    dfs = []
    if offline_df is not None and not getattr(offline_df, "empty", True):
        df = offline_df[offline_df["오더유형"] == "ZOR"].copy()
        df["채널"] = "오프라인"
        dfs.append(df)
    if online_df is not None and not getattr(online_df, "empty", True):
        df = online_df[online_df["오더유형"] == "ZOR"].copy()
        df["채널"] = "온라인"
        dfs.append(df)
    if not dfs:
        return None
    combined = pd.concat(dfs, ignore_index=True)
    combined["판매일자"] = pd.to_datetime(combined["판매일자"], format="%Y%m%d", errors="coerce")
    combined = combined.dropna(subset=["판매일자"])
    combined["주"] = combined["판매일자"].dt.to_period("W").dt.start_time
    combined["월"] = combined["판매일자"].dt.to_period("M").dt.start_time
    return combined


# ── 페이지 스코프 CSS (탭 언더라인 + expander 스타일) ──────────────────
# 사이드바/탭/expander는 Streamlit 네이티브 크롬 — 테마 토글 범위 밖(항상 다크).
st.markdown("""
<style>
.stTabs [data-baseweb="tab"] {font-weight:600; font-size:14px;}
.stTabs [aria-selected="true"] {color:#e2e8f0 !important; border-bottom-color:#2E9BE6 !important;}
[data-testid="stExpander"] {border-radius:8px; border-color:#333333;}
[data-testid="stExpander"] summary {font-weight:600; font-size:13px;}
</style>
""", unsafe_allow_html=True)

# ── 마스트헤드 ──────────────────────────────────────────────────────
col_brand, col_date, col_theme, col_dl1, col_dl2, col_new = st.columns(
    [3, 1.4, 0.6, 1.2, 1.2, 1.4]
)

with col_brand:
    st.markdown(
        f'<div style="display:flex; align-items:center; gap:10px; height:100%;">'
        f'<div style="width:34px;height:34px;border-radius:8px;background:{T["accent_soft"]};'
        f'color:{T["accent"]};display:flex;align-items:center;justify-content:center;'
        f'font-weight:700;font-family:sans-serif;">SC</div>'
        f'<div>'
        f'<div style="font-size:20px; font-weight:700; color:{T["text_primary"]};">판매일보</div>'
        f'<div style="font-size:12px; color:{T["text_tertiary"]}; margin-top:1px;">AI 매출 분석 에이전트</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

with col_date:
    st.markdown(
        f'<div style="margin-top:8px;font-size:12px;color:{T["text_secondary"]};background:{T["surface"]};'
        f'border:1px solid {T["line"]};border-radius:6px;padding:8px 12px;'
        f'font-family:monospace;text-align:center;">{report_date_display} 기준</div>',
        unsafe_allow_html=True,
    )

with col_theme:
    theme_icon = "🌙" if st.session_state["report_theme"] == "dark" else "☀️"
    if st.button(theme_icon, key="theme_toggle", help="라이트/다크 전환 (리포트 본문만)", use_container_width=True):
        st.session_state["report_theme"] = "light" if st.session_state["report_theme"] == "dark" else "dark"
        st.rerun()

html_report = state.get("html_report", "")
excel_path = state.get("excel_path", "")

with col_dl1:
    if "html" in output_options and html_report:
        st.download_button(
            label="📧 HTML",
            data=html_report.encode("utf-8"),
            file_name=f"sales_report_{report_date_raw}.html",
            mime="text/html",
            use_container_width=True,
        )

with col_dl2:
    if "excel" in output_options and excel_path and Path(excel_path).exists():
        with open(excel_path, "rb") as f:
            st.download_button(
                label="📥 Excel",
                data=f.read(),
                file_name=f"sales_report_{report_date_raw}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

with col_new:
    if st.button("🔄 새 리포트", use_container_width=True):
        del st.session_state["result_state"]
        del st.session_state["run_config"]
        st.switch_page("pages/1_upload.py")

if state.get("email_sent"):
    st.caption("✅ 이메일이 성공적으로 발송되었습니다.")

st.markdown(f"<div style='border-bottom:1px solid {T['line']}; margin:6px 0 18px;'></div>", unsafe_allow_html=True)

if db_skipped_count > 0:
    st.caption(f"ℹ️ 이미 저장된 데이터 {db_skipped_count}건 스킵 (중복 업로드)")

errors = state.get("errors", [])
if errors:
    with st.expander(f"⚠️ 처리 중 경고 {len(errors)}건", expanded=False):
        for e in errors:
            st.warning(e)

if state.get("no_data_for_date"):
    st.error(
        f"선택한 날짜({report_date_display})에 해당하는 데이터가 업로드 파일에서 "
        "발견되지 않았습니다. 날짜를 다시 확인해주세요."
    )
    st.page_link("pages/1_upload.py", label="← 업로드 페이지로 이동")
    st.stop()


# ── 탭 ────────────────────────────────────────────────────────────────
tab_brief, tab_trend = st.tabs(["오늘의 브리핑", "추이 분석"])

with tab_brief:

    # ── KPI 스트립 ────────────────────────────────────────────────────
    forecast = patterns.get("forecast", {})
    forecast_pct = forecast.get("forecast_achievement_pct")
    monthly_pct = target_summary.get("total_achievement_pct")

    def _cell(label, value, color=None):
        color_style = f"color:{color};" if color else f"color:{T['text_primary']};"
        return (
            f'<div style="background:{T["surface"]};padding:14px 12px;">'
            f'<div style="font-size:11px;color:{T["text_tertiary"]};margin-bottom:6px;">{label}</div>'
            f'<div style="font-size:18px;font-weight:600;font-family:monospace;{color_style}">{value}</div>'
            f'</div>'
        )

    anomaly_count = len(anomalies)
    anomaly_color = T['danger'] if anomaly_count > 0 else T['success']

    cells = [
        _cell("순영수증", f"{kpi_total.get('net_receipt', 0):,}건"),
        _cell("총매출", f"{kpi_total.get('total_sales', 0):,.0f}원"),
        _cell("총포인트", f"{kpi_total.get('total_point', 0):,.0f}P"),
        _cell("이상치", f"{anomaly_count}건", anomaly_color),
        _cell("월누계 달성률", f"{monthly_pct}%" if monthly_pct is not None else "—", T['accent']),
        _cell("월말 예측", f"{forecast_pct}%" if forecast_pct is not None else "—",
              T['success'] if (forecast_pct or 0) >= 90 else T['accent']),
    ]
    st.markdown(
        f'<div style="display:grid;grid-template-columns:repeat(6,1fr);gap:1px;background:{T["line"]};'
        f'border:1px solid {T["line"]};border-radius:8px;overflow:hidden;margin-bottom:20px;">'
        f'{"".join(cells)}'
        f'</div>',
        unsafe_allow_html=True,
    )

    forecast_summary = esc(insights.get("forecast_summary", ""))
    if forecast_summary:
        st.caption(f"📈 {forecast_summary}")

    # ── 오늘의 핵심 이슈 (헤드라인 카드) ─────────────────────────────
    def _issue_detail(category: str) -> tuple:
        """category별 rule 수치로 상세문장·태그 생성. LLM 아님 — 이스케이프 불필요."""
        if category == "목표미달":
            adt = patterns.get("adjusted_daily_target", {})
            sev = adt.get("severity", "low")
            detail = (
                f"조정 일별 목표 {adt.get('adjusted_daily_required', 0):,}원 대비 "
                f"오늘 순매출 {adt.get('today_net_sales', 0):,}원."
            )
            tags = [
                f"잔여 {adt.get('days_remaining', 0)}일",
                f"일평균 필요 {adt.get('adjusted_daily_required', 0):,}원",
            ]
            return sev, detail, tags
        if category == "반품이슈":
            ra = patterns.get("return_anomalies", [])
            if ra:
                top = ra[0]
                sev = top.get("severity", "medium")
                detail = (
                    f"{top.get('product_name', '')} 오늘 반품 {top.get('today_returns', 0)}건, "
                    f"평소 대비 {top.get('multiplier', 0)}배."
                )
                tags = [
                    f"오늘 반품금액 {top.get('today_return_amount', 0):,}원",
                    f"평소 반품률 {top.get('hist_rate', 0) * 100:.1f}%",
                ]
                return sev, detail, tags
            return "medium", "", []
        if category == "수익성문제":
            d = patterns.get("discount_sensitivity", {})
            dev = d.get("margin_deviation")
            detail = (
                f"실제 마진율 {d.get('margin_pct_overall', '—')}% "
                f"(이론 대비 {dev}%p)"
            ) if dev is not None else ""
            return "medium", detail, []
        if category == "추세악화":
            t = patterns.get("trend_direction_30d", {})
            detail = f"30일 방향 {t.get('overall_direction', '')}, 가속도 z={t.get('accel_zscore', '—')}"
            return "medium", detail, []
        return "medium", "", []

    top_issues = insights.get("top_issues", [])
    if top_issues:
        st.markdown("<div style='font-size:14px;font-weight:600;text-transform:uppercase;"
                     f"letter-spacing:.05em;color:{T['text_secondary']};margin-bottom:10px;'>"
                     "오늘의 핵심 이슈</div>", unsafe_allow_html=True)

        for item in top_issues:
            category = item.get("category", "기타")
            issue_text = esc(item.get("issue", ""))
            sev, detail, tags = _issue_detail(category)
            badge_bg = T['danger_soft'] if sev == "high" else T['surface_raised']
            badge_fg = T['danger'] if sev == "high" else T['text_secondary']
            badge_label = "심각" if sev == "high" else "주의"
            tags_html = "".join(
                f'<span style="font-size:11px;color:{T["text_tertiary"]};background:{T["surface_raised"]};'
                f'border-radius:4px;padding:3px 8px;font-family:monospace;margin-right:6px;">{esc(tg)}</span>'
                for tg in tags
            )
            detail_html = (
                f'<p style="font-size:13px;color:{T["text_secondary"]};margin:0 0 10px;">{detail}</p>'
                if detail else ''
            )
            tags_div_html = f'<div>{tags_html}</div>' if tags_html else ''
            st.markdown(
                f'<div style="background:{T["surface"]};border:1px solid {T["line"]};border-radius:8px;'
                f'border-left:4px solid {T["danger"]};padding:16px 18px;margin-bottom:10px;">'
                f'<div style="display:flex;justify-content:space-between;margin-bottom:8px;">'
                f'<span style="font-size:11px;font-weight:600;padding:3px 9px;border-radius:20px;'
                f'background:{badge_bg};color:{badge_fg};">{badge_label}</span>'
                f'<span style="font-size:11px;color:{T["text_tertiary"]};background:{T["surface_raised"]};'
                f'border-radius:4px;padding:3px 8px;font-family:monospace;">{esc(category)}</span>'
                f'</div>'
                f'<h3 style="font-size:16px;font-weight:600;margin:6px 0;color:{T["text_primary"]};">{issue_text}</h3>'
                f'{detail_html}{tags_div_html}'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ── 이상치 리스트 (목표 미달/초과 + 기타 이상치) ─────────────────
    low_ach = [a for a in anomalies if a.get("type") == "low_achievement"]
    other_anoms = [a for a in anomalies if a.get("type") != "low_achievement"]
    target_by_platform = {p["platform"]: p for p in target_summary.get("by_platform", [])}
    over_ach = [p for p in target_summary.get("by_platform", []) if p.get("achievement_pct", 0) >= 100]

    if anomalies:
        st.markdown(f"<div style='font-size:14px;font-weight:600;text-transform:uppercase;"
                     f"letter-spacing:.05em;color:{T['text_secondary']};margin:24px 0 10px;'>"
                     f"이상치 {len(anomalies)}건 · 확인 필요</div>", unsafe_allow_html=True)

        for a in low_ach:
            platform = a.get("platform", "")
            pt = target_by_platform.get(platform, {})
            pct = pt.get("achievement_pct", 0)
            dot = get_store_color(platform)
            st.markdown(
                f'<div style="background:{T["surface"]};border:1px solid {T["line"]};border-radius:8px;'
                f'border-left:4px solid {T["danger"]};padding:16px 18px;margin-bottom:10px;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;gap:16px;">'
                f'<div style="flex:1;display:flex;align-items:center;font-size:14px;font-weight:600;color:{T["text_primary"]};">'
                f'<span style="width:8px;height:8px;border-radius:50%;background:{dot};display:inline-block;margin-right:7px;"></span>'
                f'{esc(platform)}</div>'
                f'<div style="flex:2;font-size:12.5px;color:{T["text_secondary"]};">'
                f'월 달성률 {pct}% · 기준(70%) 미달 · 일평균 {pt.get("daily_required", 0):,}원 필요</div>'
                f'<div style="width:110px;height:6px;background:{T["surface_raised"]};border-radius:3px;overflow:hidden;flex-shrink:0;">'
                f'<div style="height:100%;border-radius:3px;background:{T["danger"]};width:{min(pct,100)}%;"></div></div>'
                f'<div style="font-family:monospace;font-size:13px;font-weight:600;min-width:52px;text-align:right;color:{T["danger"]};">{pct}%</div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

        for a in other_anoms:
            sev_color = T['danger'] if a.get("severity") == "warning" else T['text_secondary']
            dot = get_store_color(a.get("platform", ""))
            st.markdown(
                f'<div style="background:{T["surface"]};border:1px solid {T["line"]};border-radius:8px;'
                f'border-left:4px solid {sev_color};padding:14px 18px;margin-bottom:10px;">'
                f'<div style="display:flex;align-items:center;font-size:13px;color:{T["text_secondary"]};">'
                f'<span style="width:8px;height:8px;border-radius:50%;background:{dot};display:inline-block;margin-right:7px;"></span>'
                f'{esc(a.get("message", ""))}</div></div>',
                unsafe_allow_html=True,
            )

        for pt in over_ach:
            platform = pt["platform"]
            dot = get_store_color(platform)
            pct = pt.get("achievement_pct", 0)
            st.markdown(
                f'<div style="background:{T["surface"]};border:1px solid {T["line"]};border-radius:8px;'
                f'border-left:4px solid {T["success"]};padding:16px 18px;margin-bottom:10px;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;gap:16px;">'
                f'<div style="flex:1;display:flex;align-items:center;font-size:14px;font-weight:600;color:{T["text_primary"]};">'
                f'<span style="width:8px;height:8px;border-radius:50%;background:{dot};display:inline-block;margin-right:7px;"></span>'
                f'{esc(platform)} — 목표 초과 달성</div>'
                f'<div style="flex:2;font-size:12.5px;color:{T["text_secondary"]};">'
                f'월 달성률 {pct}% · 잔여 목표 없음, 이례적 호실적</div>'
                f'<div style="width:110px;height:6px;background:{T["surface_raised"]};border-radius:3px;overflow:hidden;flex-shrink:0;">'
                f'<div style="height:100%;border-radius:3px;background:{T["success"]};width:100%;"></div></div>'
                f'<div style="font-family:monospace;font-size:13px;font-weight:600;min-width:52px;text-align:right;color:{T["success"]};">{pct}%</div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

    # ── 오늘 할 일 ────────────────────────────────────────────────────
    if actions:
        st.markdown(f"<div style='font-size:14px;font-weight:600;text-transform:uppercase;"
                     f"letter-spacing:.05em;color:{T['text_secondary']};margin:24px 0 10px;'>"
                     f"오늘 할 일</div>", unsafe_allow_html=True)

        for a in actions:
            timing = a.get("timing", "")
            if "오늘" in timing:
                tag_bg, tag_fg = T['danger_soft'], T['danger']
            elif "주" in timing:
                tag_bg, tag_fg = T['surface_raised'], T['text_secondary']
            else:
                tag_bg, tag_fg = T['accent_soft'], T['accent']

            st.markdown(
                f'<div style="display:flex;gap:14px;align-items:flex-start;background:{T["surface"]};'
                f'border:1px solid {T["line"]};border-radius:8px;padding:14px 16px;margin-bottom:8px;">'
                f'<div style="display:flex;flex-direction:column;gap:6px;flex-shrink:0;width:110px;">'
                f'<span style="font-size:11px;font-weight:600;padding:3px 9px;border-radius:20px;'
                f'background:{tag_bg};color:{tag_fg};text-align:center;">{esc(timing)}</span>'
                f'<span style="font-size:11px;color:{T["text_tertiary"]};background:{T["surface_raised"]};'
                f'border-radius:4px;padding:3px 8px;font-family:monospace;text-align:center;">{esc(a.get("owner", ""))}</span>'
                f'</div>'
                f'<div style="font-size:13.5px;line-height:1.55;color:{T["text_primary"]};">{esc(a.get("action", ""))}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ── 플랫폼별 매출 차트 ────────────────────────────────────────────
    def _build_bar_chart_html(records: list) -> str:
        if not records:
            return (f'<html><body style="background:{T["bg"]};margin:0;display:flex;'
                     f'align-items:center;justify-content:center;height:260px;">'
                     f'<p style="color:{T["text_tertiary"]};font-family:sans-serif;">데이터 없음</p></body></html>')

        W, H = 580, 310
        mt, mr, mb, ml = 20, 20, 90, 55
        pw, ph = W - ml - mr, H - mt - mb

        n = len(records)
        bar_group = pw / n
        bar_w = bar_group * 0.62
        max_val = max(r["total_sales"] for r in records) or 1

        bars = []
        for i, rec in enumerate(records):
            pct = rec["total_sales"] / max_val
            bh = max(ph * pct, 2)
            x = ml + i * bar_group + (bar_group - bar_w) / 2
            y = mt + ph - bh
            color = get_store_color(rec["platform"])
            val_man = rec["total_sales"] // 10000
            label = rec["platform"]

            bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{color}" rx="4" opacity="0.9"/>')
            if val_man > 0:
                bars.append(f'<text x="{x+bar_w/2:.1f}" y="{y-6:.1f}" text-anchor="middle" fill="{T["text_secondary"]}" font-size="11" font-family="sans-serif">{val_man:,}만</text>')

            cx_bar = x + bar_w / 2
            label_y = H - mb + 14
            bars.append(
                f'<text x="{cx_bar:.1f}" y="{label_y:.1f}" text-anchor="end" '
                f'transform="rotate(-35 {cx_bar:.1f} {label_y:.1f})" '
                f'fill="{T["text_tertiary"]}" font-size="10" font-family="sans-serif">{label}</text>'
            )

        y_lines = []
        for i in range(5):
            y_pos = mt + ph * i / 4
            val = int(max_val * (4 - i) / 4 / 10000)
            y_lines.append(f'<line x1="{ml}" y1="{y_pos:.1f}" x2="{W-mr}" y2="{y_pos:.1f}" stroke="{T["surface_raised"]}" stroke-width="1"/>')
            y_lines.append(f'<text x="{ml-6}" y="{y_pos+4:.1f}" text-anchor="end" fill="{T["text_tertiary"]}" font-size="10" font-family="sans-serif">{val:,}만</text>')

        svg = (
            f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:100%;">'
            f'{"".join(y_lines)}{"".join(bars)}</svg>'
        )
        return f'<!DOCTYPE html><html><head><style>body{{margin:0;background:{T["bg"]};overflow:hidden;}}</style></head><body>{svg}</body></html>'

    st.markdown(f"<div style='font-size:14px;font-weight:600;text-transform:uppercase;"
                 f"letter-spacing:.05em;color:{T['text_secondary']};margin:24px 0 10px;'>"
                 f"플랫폼별 매출 (당일)</div>", unsafe_allow_html=True)

    if by_platform:
        legend_items = "".join(
            f'<span style="display:inline-flex;align-items:center;gap:6px;margin-right:16px;font-size:12px;color:{T["text_secondary"]};">'
            f'<i style="width:9px;height:9px;border-radius:2px;background:{get_store_color(r["platform"])};display:inline-block;"></i>{esc(r["platform"])}</span>'
            for r in by_platform
        )
        st.markdown(f"<div style='margin-bottom:8px;'>{legend_items}</div>", unsafe_allow_html=True)
        components.html(_build_bar_chart_html(by_platform), height=328)
    else:
        st.info("KPI 데이터가 없습니다.")

    # ── 플랫폼별 목표 달성률 ──────────────────────────────────────────
    st.markdown(f"<div style='font-size:14px;font-weight:600;text-transform:uppercase;"
                 f"letter-spacing:.05em;color:{T['text_secondary']};margin:24px 0 10px;'>"
                 f"플랫폼별 목표 달성률</div>", unsafe_allow_html=True)

    if target_summary and target_summary.get("total_target", 0) > 0:
        is_cumulative = bool(kpi_cumulative and kpi_cumulative.get("by_platform"))
        basis_label = "월 누계 기준" if is_cumulative else "당일 기준"

        total_pct = target_summary.get("total_achievement_pct", 0)
        color = T['success'] if total_pct >= 100 else (T['accent'] if total_pct >= 70 else T['danger'])
        daily_line = (
            f" · 당일 매출: {kpi_total.get('total_sales', 0):,}원" if is_cumulative else ""
        )
        st.markdown(
            f'<div style="background:{T["surface"]};border:1px solid {T["line"]};border-radius:8px;padding:14px 18px;margin-bottom:10px;">'
            f'<div style="font-size:12px;color:{T["text_tertiary"]};margin-bottom:4px;">'
            f'전체 달성률 — {target_summary.get("month", "")} ({basis_label})</div>'
            f'<div style="font-size:24px;font-weight:700;color:{color};">{total_pct}%</div>'
            f'<div style="font-size:12px;color:{T["text_secondary"]};margin-top:2px;">'
            f'월 누계: {target_summary.get("total_actual", 0):,} / {target_summary.get("total_target", 0):,}원{daily_line}'
            f' · 잔여 {target_summary.get("days_remaining", 0)}일'
            f' · 일평균 {target_summary.get("daily_required", 0):,}원 필요</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        rows_html = ""
        targeted_platforms = set()
        for pt in target_summary.get("by_platform", []):
            targeted_platforms.add(pt["platform"])
            pct = pt.get("achievement_pct", 0)
            dot = get_store_color(pt["platform"])
            row_color = T['success'] if pct >= 100 else (T['danger'] if pt.get("flag") == "low_achievement" else T['text_primary'])
            fill_color = T['success'] if pct >= 100 else (T['danger'] if pt.get("flag") == "low_achievement" else T['accent'])
            daily_req_txt = (
                '잔여 목표 없음' if pct >= 100 else f"일평균 {pt.get('daily_required', 0):,}원 필요"
            )
            rows_html += (
                f'<div style="display:flex;align-items:center;gap:14px;padding:10px 0;border-bottom:1px solid {T["line"]};">'
                f'<div style="width:160px;font-size:13.5px;font-weight:500;flex-shrink:0;display:flex;align-items:center;color:{T["text_primary"]};">'
                f'<span style="width:8px;height:8px;border-radius:50%;background:{dot};display:inline-block;margin-right:7px;"></span>{esc(pt["platform"])}</div>'
                f'<div style="flex:1;height:8px;background:{T["surface_raised"]};border-radius:4px;overflow:hidden;">'
                f'<div style="height:100%;border-radius:4px;background:{fill_color};width:{min(pct,100)}%;"></div></div>'
                f'<div style="width:56px;text-align:right;font-family:monospace;font-size:13px;font-weight:600;flex-shrink:0;color:{row_color};">{pct}%</div>'
                f'<div style="width:190px;font-size:11px;color:{T["text_tertiary"]};flex-shrink:0;text-align:right;">{daily_req_txt}</div>'
                f'</div>'
            )

        for r in by_platform:
            if r["platform"] in targeted_platforms:
                continue
            dot = get_store_color(r["platform"])
            rows_html += (
                f'<div style="display:flex;align-items:center;gap:14px;padding:10px 0;border-bottom:1px solid {T["line"]};">'
                f'<div style="width:160px;font-size:13.5px;font-weight:500;flex-shrink:0;display:flex;align-items:center;color:{T["text_primary"]};">'
                f'<span style="width:8px;height:8px;border-radius:50%;background:{dot};display:inline-block;margin-right:7px;"></span>{esc(r["platform"])}</div>'
                f'<div style="flex:1;height:8px;background:{T["surface_raised"]};border-radius:4px;overflow:hidden;"></div>'
                f'<div style="width:56px;text-align:right;">'
                f'<span style="font-size:11px;font-weight:600;padding:3px 9px;border-radius:20px;background:{T["surface_raised"]};color:{T["text_secondary"]};">미설정</span></div>'
                f'<div style="width:190px;"></div>'
                f'</div>'
            )

        st.markdown(
            f'<div style="background:{T["surface"]};border:1px solid {T["line"]};border-radius:8px;padding:6px 18px;margin-bottom:10px;">'
            f'{rows_html}'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div style="background:{T["surface"]};border:1px solid {T["line"]};border-radius:8px;padding:20px;text-align:center;margin-bottom:12px;">'
            f'<div style="font-size:14px;font-weight:600;color:{T["text_primary"]};margin-bottom:6px;">목표 미설정</div>'
            f'<div style="font-size:12.5px;color:{T["text_tertiary"]};">이번 달 목표 매출을 입력하면 달성률을 확인할 수 있습니다.</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        with st.form("quick_target_form"):
            st.caption("월 전체 타겟을 입력하세요 (플랫폼별 상세는 config.py에서 설정 가능)")
            form_total_target = st.number_input("월 전체 타겟 (원)", min_value=0, value=0, step=1_000_000, format="%d")
            submitted = st.form_submit_button("달성률 계산", type="primary")

        if submitted and form_total_target > 0:
            year = int(report_date_raw[:4])
            month_num = int(report_date_raw[4:6])
            day_of_month = int(report_date_raw[6:8]) if len(report_date_raw) >= 8 else 1
            total_days = monthrange(year, month_num)[1]
            days_remaining = max(total_days - day_of_month, 0)
            month_key = f"{report_date_raw[:4]}-{report_date_raw[4:6]}"

            is_cumulative = bool(kpi_cumulative and kpi_cumulative.get("by_platform"))
            if is_cumulative:
                total_actual = int(sum(r.get("total_revenue", 0) for r in kpi_cumulative["by_platform"]))
            else:
                total_actual = kpi_total.get("total_sales", 0)

            remaining = max(form_total_target - total_actual, 0)
            daily_req = int(remaining / days_remaining) if days_remaining > 0 else 0
            total_pct = round(total_actual / form_total_target * 100, 1)

            computed_target = {
                "month": month_key,
                "total_target": form_total_target,
                "total_actual": total_actual,
                "total_achievement_pct": total_pct,
                "days_remaining": days_remaining,
                "daily_required": daily_req,
                "by_platform": [],
            }
            st.session_state["result_state"] = {**state, "target_summary": computed_target}
            st.rerun()

    # ── AI 코멘터리 ───────────────────────────────────────────────────
    llm_commentary = state.get("llm_commentary", "")
    if llm_commentary:
        with st.expander("AI 코멘터리 전문 보기"):
            st.caption(LLM_MODEL.upper())
            st.markdown(f"<div style='font-size:14px;line-height:1.8;color:{T['text_secondary']};'>{esc(llm_commentary)}</div>",
                        unsafe_allow_html=True)


with tab_trend:
    offline_proc = state.get("offline_processed")
    online_proc = state.get("online_processed")
    ts = _prepare_time_series(offline_proc, online_proc)

    is_dark = st.session_state["report_theme"] == "dark"
    plotly_template = "plotly_dark" if is_dark else "plotly_white"
    PAPER_BG = T['bg']
    PLOT_BG = T['surface']
    GRID = "rgba(128,128,128,0.2)"

    if ts is None or ts.empty:
        st.info("데이터를 먼저 로드해주세요.")
    else:
        st.markdown(f"<div style='font-size:14px;font-weight:600;color:{T['text_primary']};margin-bottom:8px;'>채널별 매출 추이</div>",
                    unsafe_allow_html=True)

        unique_days = ts["판매일자"].dt.normalize().nunique()
        if unique_days < 2:
            st.info(f"현재 {unique_days}일치 데이터만 있어 추이 차트를 그릴 수 없습니다. "
                    "리포트를 여러 날짜에 걸쳐 생성하면(최소 2일 이상) 이 차트가 표시됩니다.")
        else:
            period_opt = st.radio("집계 단위", ["일별", "주별", "월별"], horizontal=True, key="ts_period")
            period_col = {"일별": "판매일자", "주별": "주", "월별": "월"}[period_opt]

            grp = ts.groupby([period_col, "채널"], as_index=False)["매출"].sum()
            fig1 = px.line(
                grp, x=period_col, y="매출", color="채널",
                color_discrete_map={"오프라인": T['accent'], "온라인": T['gray_2']},
                template=plotly_template,
            )
            fig1.update_layout(
                paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
                margin=dict(l=0, r=0, t=20, b=0),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            fig1.update_yaxes(showgrid=True, gridcolor=GRID, tickformat=",")
            fig1.update_xaxes(showgrid=False)
            st.plotly_chart(fig1, use_container_width=True)

        col_c1, col_c2 = st.columns(2)

        with col_c1:
            st.markdown(f"<div style='font-size:14px;font-weight:600;color:{T['text_primary']};margin-bottom:8px;'>플랫폼별 매출 비중</div>",
                        unsafe_allow_html=True)
            if by_platform:
                pie_colors = [get_store_color(r["platform"]) for r in by_platform]
                if len(set(pie_colors)) <= 1:
                    # 지역 키워드 무매칭 시 get_store_color가 전부 동일 회색을 반환 —
                    # 파이차트는 인접 조각이 구분 안 되므로 text_tertiary~text_primary
                    # 사이를 플랫폼 수만큼 등분한 회색조로 대체(개수와 무관하게 안 겹침).
                    pie_colors = _gray_ramp(T, len(by_platform))
                fig2 = px.pie(
                    values=[r["total_sales"] for r in by_platform],
                    names=[r["platform"] for r in by_platform],
                    template=plotly_template,
                    color_discrete_sequence=pie_colors,
                )
                fig2.update_layout(paper_bgcolor=PAPER_BG, margin=dict(l=0, r=0, t=20, b=0))
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("플랫폼 데이터 없음")

        with col_c2:
            st.markdown(f"<div style='font-size:14px;font-weight:600;color:{T['text_primary']};margin-bottom:8px;'>중분류별 매출 TOP10</div>",
                        unsafe_allow_html=True)
            by_category = kpi_summary.get("by_category", [])
            if by_category:
                l2_map: dict = {}
                for item in by_category:
                    l2 = item["category_l2"]
                    l2_map[l2] = l2_map.get(l2, 0) + item["total_sales"]
                sorted_l2 = sorted(l2_map.items(), key=lambda x: x[1])[-10:]
                fig3 = px.bar(
                    x=[v for _, v in sorted_l2],
                    y=[k for k, _ in sorted_l2],
                    orientation="h",
                    template=plotly_template,
                    color_discrete_sequence=[T['accent']],
                )
                fig3.update_layout(paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG, margin=dict(l=0, r=0, t=20, b=0))
                fig3.update_xaxes(tickformat=",", showgrid=True, gridcolor=GRID)
                fig3.update_yaxes(showgrid=False)
                st.plotly_chart(fig3, use_container_width=True)
            else:
                st.info("카테고리 데이터 없음")

        st.markdown(f"<div style='font-size:14px;font-weight:600;color:{T['text_primary']};margin-bottom:8px;'>제품별 매출 TOP10</div>",
                    unsafe_allow_html=True)
        by_product = kpi_summary.get("by_product", [])
        if by_product:
            top10 = list(reversed(by_product[:10]))
            fig4 = px.bar(
                x=[p["total_sales"] for p in top10],
                y=[p["product_name"] for p in top10],
                orientation="h",
                template=plotly_template,
                color_discrete_sequence=[T['accent']],
            )
            fig4.update_layout(paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG, margin=dict(l=0, r=0, t=20, b=0), height=360)
            fig4.update_xaxes(tickformat=",", showgrid=True, gridcolor=GRID)
            fig4.update_yaxes(showgrid=False)
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info("제품 데이터 없음")
