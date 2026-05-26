from calendar import monthrange
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from dotenv import load_dotenv

from utils.styles import inject_global_css, render_sidebar_brand

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
anomalies = state.get("anomalies", [])
db_skipped_count = state.get("db_skipped_count", 0)

OFFLINE_PLATFORMS = {"HCC", "HCC 부산점", "HCC 제주점"}


def get_channel(platform: str) -> str:
    return "오프라인" if platform in OFFLINE_PLATFORMS else "온라인"


# ── 헤더 ─────────────────────────────────────────────────────────────
col_h, col_btn = st.columns([6, 1])
with col_h:
    st.markdown(f"""
    <div style="display:flex; align-items:center; margin-bottom:20px;">
        <div>
            <div style="font-size:22px; font-weight:700; color:#e2e8f0;">판매일보</div>
            <div style="font-size:13px; color:#718096; margin-top:3px;">{report_date_display} 기준 · AI 자동 생성</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
with col_btn:
    if st.button("🔄 새 리포트", use_container_width=True):
        del st.session_state["result_state"]
        del st.session_state["run_config"]
        st.switch_page("pages/1_upload.py")

errors = state.get("errors", [])
if errors:
    with st.expander(f"⚠️ 처리 중 경고 {len(errors)}건", expanded=False):
        for e in errors:
            st.warning(e)


# ── KPI 카드 4개 ──────────────────────────────────────────────────────
def render_kpi_cards(net_receipt: int, total_sales: int, total_point: int, anomaly_count: int):
    anomaly_color = "#f59e0b" if anomaly_count > 0 else "#10b981"
    anomaly_label = "확인 필요" if anomaly_count > 0 else "정상"
    st.markdown(f"""
    <div style="display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:28px;">
        <div style="background:#1e1e2e; border-radius:12px; padding:18px 20px; border-left:3px solid #3b82f6;">
            <div style="font-size:11px; color:#718096; letter-spacing:0.8px; text-transform:uppercase; margin-bottom:8px;">순영수증</div>
            <div style="font-size:28px; font-weight:700; color:#e2e8f0;">{net_receipt:,}건</div>
            <div style="font-size:11px; color:#4a5568; margin-top:4px;">ZOR - ZRE</div>
        </div>
        <div style="background:#1e1e2e; border-radius:12px; padding:18px 20px; border-left:3px solid #10b981;">
            <div style="font-size:11px; color:#718096; letter-spacing:0.8px; text-transform:uppercase; margin-bottom:8px;">총매출</div>
            <div style="font-size:28px; font-weight:700; color:#e2e8f0;">{total_sales:,.0f}원</div>
            <div style="font-size:11px; color:#4a5568; margin-top:4px;">HCC + 헬리녹스</div>
        </div>
        <div style="background:#1e1e2e; border-radius:12px; padding:18px 20px; border-left:3px solid #8b5cf6;">
            <div style="font-size:11px; color:#718096; letter-spacing:0.8px; text-transform:uppercase; margin-bottom:8px;">총포인트</div>
            <div style="font-size:28px; font-weight:700; color:#e2e8f0;">{total_point:,.0f}P</div>
            <div style="font-size:11px; color:#4a5568; margin-top:4px;">전 플랫폼 합산</div>
        </div>
        <div style="background:#1e1e2e; border-radius:12px; padding:18px 20px; border-left:3px solid {anomaly_color};">
            <div style="font-size:11px; color:#718096; letter-spacing:0.8px; text-transform:uppercase; margin-bottom:8px;">이상치</div>
            <div style="font-size:28px; font-weight:700; color:{anomaly_color};">{anomaly_count}건</div>
            <div style="font-size:11px; color:{anomaly_color}; margin-top:4px;">{anomaly_label}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


render_kpi_cards(
    kpi_total.get("net_receipt", 0),
    kpi_total.get("total_sales", 0),
    kpi_total.get("total_point", 0),
    len(anomalies),
)


# ── SVG 바 차트 ───────────────────────────────────────────────────────
def _build_bar_chart_html(records: list) -> str:
    if not records:
        return '<html><body style="background:#16162a;margin:0;display:flex;align-items:center;justify-content:center;height:260px;"><p style="color:#718096;font-family:sans-serif;">데이터 없음</p></body></html>'

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
        color = "#3b82f6" if rec["platform"] in OFFLINE_PLATFORMS else "#10b981"
        val_man = rec["total_sales"] // 10000
        label = rec["platform"]

        bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{color}" rx="4" opacity="0.9"/>')
        if val_man > 0:
            bars.append(f'<text x="{x+bar_w/2:.1f}" y="{y-6:.1f}" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="sans-serif">{val_man:,}만</text>')

        cx_bar = x + bar_w / 2
        label_y = H - mb + 14
        bars.append(
            f'<text x="{cx_bar:.1f}" y="{label_y:.1f}" text-anchor="end" '
            f'transform="rotate(-35 {cx_bar:.1f} {label_y:.1f})" '
            f'fill="#718096" font-size="10" font-family="sans-serif">{label}</text>'
        )

    y_lines = []
    for i in range(5):
        y_pos = mt + ph * i / 4
        val = int(max_val * (4 - i) / 4 / 10000)
        y_lines.append(f'<line x1="{ml}" y1="{y_pos:.1f}" x2="{W-mr}" y2="{y_pos:.1f}" stroke="#1e1e2e" stroke-width="1"/>')
        y_lines.append(f'<text x="{ml-6}" y="{y_pos+4:.1f}" text-anchor="end" fill="#4a5568" font-size="10" font-family="sans-serif">{val:,}만</text>')

    legend = (
        f'<rect x="{W-mr-110}" y="{mt}" width="10" height="10" fill="#3b82f6" rx="2"/>'
        f'<text x="{W-mr-96}" y="{mt+9}" fill="#718096" font-size="10" font-family="sans-serif">오프라인</text>'
        f'<rect x="{W-mr-45}" y="{mt}" width="10" height="10" fill="#10b981" rx="2"/>'
        f'<text x="{W-mr-31}" y="{mt+9}" fill="#718096" font-size="10" font-family="sans-serif">온라인</text>'
    )

    svg = (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;height:100%;">'
        f'{"".join(y_lines)}'
        f'{"".join(bars)}'
        f'{legend}'
        f'</svg>'
    )
    return f'<!DOCTYPE html><html><head><style>body{{margin:0;background:#16162a;overflow:hidden;}}</style></head><body>{svg}</body></html>'


# ── SVG 게이지 ────────────────────────────────────────────────────────
def _build_gauge_html(pct: float, total_actual: int, total_target: int, days_remaining: int, daily_required: int) -> str:
    color = "#10b981" if pct >= 90 else ("#3b82f6" if pct >= 70 else "#f59e0b")
    circumference = 251.2
    dash_fill = f"{circumference * min(max(pct, 0), 100) / 100:.1f} {circumference}"

    actual_man = total_actual // 10000
    target_man = total_target // 10000
    daily_man = daily_required // 10000

    pct_text = f"{pct:.1f}%"
    desc_text = f"{actual_man:,}만 / {target_man:,}만원"
    bottom_text = f"남은 {days_remaining}일 · 일평균 {daily_man:,}만원 필요"

    svg = f"""<svg viewBox="0 0 200 120" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:200px;display:block;margin:0 auto;">
  <path d="M20,100 A80,80 0 0,1 180,100" fill="none" stroke="#2d3748" stroke-width="16" stroke-linecap="round"/>
  <path d="M20,100 A80,80 0 0,1 180,100" fill="none" stroke="{color}" stroke-width="16" stroke-linecap="round"
        stroke-dasharray="{dash_fill}"/>
  <text x="100" y="90" text-anchor="middle" fill="{color}" font-size="24" font-weight="600" font-family="sans-serif">{pct_text}</text>
  <text x="100" y="110" text-anchor="middle" fill="#718096" font-size="11" font-family="sans-serif">{desc_text}</text>
</svg>"""

    return (
        f'<!DOCTYPE html><html><head><style>'
        f'body{{margin:0;background:#0f0f1a;overflow:hidden;text-align:center;font-family:sans-serif;}}'
        f'.bt{{font-size:12px;color:#718096;margin-top:4px;}}'
        f'</style></head><body>'
        f'{svg}'
        f'<div class="bt">{bottom_text}</div>'
        f'</body></html>'
    )


# ── 바 차트 + 게이지 ──────────────────────────────────────────────────
by_platform = kpi_summary.get("by_platform", [])

col_chart, col_gauge = st.columns([2, 1])

with col_chart:
    st.markdown('<div style="color:#e2e8f0;font-size:14px;font-weight:600;margin-bottom:8px;">플랫폼별 매출 (당일)</div>', unsafe_allow_html=True)
    chart_html = _build_bar_chart_html(by_platform)
    components.html(chart_html, height=328)

with col_gauge:
    st.markdown('<div style="color:#e2e8f0;font-size:14px;font-weight:600;margin-bottom:8px;">타겟 달성률</div>', unsafe_allow_html=True)
    if target_summary and target_summary.get("total_target", 0) > 0:
        gauge_html = _build_gauge_html(
            pct=target_summary.get("total_achievement_pct", 0),
            total_actual=target_summary.get("total_actual", 0),
            total_target=target_summary.get("total_target", 0),
            days_remaining=target_summary.get("days_remaining", 0),
            daily_required=target_summary.get("daily_required", 0),
        )
        components.html(gauge_html, height=175)
    else:
        components.html(
            '<!DOCTYPE html><html><head><style>body{margin:0;background:#0f0f1a;display:flex;align-items:center;justify-content:center;height:175px;}</style></head>'
            '<body><div style="text-align:center;color:#4a5568;font-family:sans-serif;font-size:13px;">타겟 미설정<br><span style="font-size:11px;">아래 탭에서 입력하세요</span></div></body></html>',
            height=175,
        )

st.divider()

# ── 플랫폼 상세 테이블 ────────────────────────────────────────────────
st.markdown('<div style="color:#e2e8f0;font-size:14px;font-weight:600;margin-bottom:10px;">플랫폼별 상세</div>', unsafe_allow_html=True)

if by_platform:
    rows_html = ""
    for i, rec in enumerate(by_platform):
        ch = get_channel(rec["platform"])
        badge_bg = "#1e40af" if ch == "오프라인" else "#065f46"
        badge_color = "#bfdbfe" if ch == "오프라인" else "#a7f3d0"
        row_bg = "#1a1a2e" if i % 2 == 0 else "#16162a"
        rows_html += f"""
        <tr style="background:{row_bg};">
            <td style="padding:9px 12px;color:#e2e8f0;">{rec['platform']}</td>
            <td style="padding:9px 12px;text-align:center;">
                <span style="background:{badge_bg};color:{badge_color};padding:2px 8px;border-radius:4px;font-size:11px;">{ch}</span>
            </td>
            <td style="padding:9px 12px;text-align:right;color:#94a3b8;">{rec['zor']:,}</td>
            <td style="padding:9px 12px;text-align:right;color:#94a3b8;">{rec['zre']:,}</td>
            <td style="padding:9px 12px;text-align:right;color:#94a3b8;">{rec['net_receipt']:,}</td>
            <td style="padding:9px 12px;text-align:right;color:#e2e8f0;font-weight:500;">{rec['total_sales']:,}원</td>
            <td style="padding:9px 12px;text-align:right;color:#94a3b8;">{rec['total_point']:,}P</td>
        </tr>"""

    t = kpi_total
    rows_html += f"""
    <tr style="background:#1e3a5f;font-weight:700;">
        <td style="padding:9px 12px;color:#e2e8f0;">합계</td>
        <td></td>
        <td style="padding:9px 12px;text-align:right;color:#94a3b8;">{sum(r['zor'] for r in by_platform):,}</td>
        <td style="padding:9px 12px;text-align:right;color:#94a3b8;">{sum(r['zre'] for r in by_platform):,}</td>
        <td style="padding:9px 12px;text-align:right;color:#94a3b8;">{t.get('net_receipt',0):,}</td>
        <td style="padding:9px 12px;text-align:right;color:#e2e8f0;">{t.get('total_sales',0):,}원</td>
        <td style="padding:9px 12px;text-align:right;color:#94a3b8;">{t.get('total_point',0):,}P</td>
    </tr>"""

    st.markdown(f"""
    <div style="overflow-x:auto;border-radius:10px;border:1px solid #1e1e2e;">
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
        <thead>
            <tr style="background:#0a0a14;">
                <th style="padding:10px 12px;text-align:left;color:#718096;font-weight:500;">플랫폼</th>
                <th style="padding:10px 12px;text-align:center;color:#718096;font-weight:500;">채널</th>
                <th style="padding:10px 12px;text-align:right;color:#718096;font-weight:500;">ZOR</th>
                <th style="padding:10px 12px;text-align:right;color:#718096;font-weight:500;">ZRE</th>
                <th style="padding:10px 12px;text-align:right;color:#718096;font-weight:500;">순영수증</th>
                <th style="padding:10px 12px;text-align:right;color:#718096;font-weight:500;">총매출</th>
                <th style="padding:10px 12px;text-align:right;color:#718096;font-weight:500;">포인트</th>
            </tr>
        </thead>
        <tbody>{rows_html}</tbody>
    </table>
    </div>
    """, unsafe_allow_html=True)
else:
    st.info("KPI 데이터가 없습니다.")

st.divider()

# ── 탭 ────────────────────────────────────────────────────────────────
tab_labels = []
if "html" in output_options:
    tab_labels.append("📧 HTML 미리보기")
tab_labels.append("🎯 타겟 달성현황")
if anomalies:
    tab_labels.append("⚠️ 이상치")
if state.get("llm_commentary"):
    tab_labels.append("🤖 AI 코멘터리")
tab_labels.append("📥 다운로드")

tabs = st.tabs(tab_labels)
tab_idx = 0

# HTML 미리보기
if "html" in output_options:
    with tabs[tab_idx]:
        html_report = state.get("html_report", "")
        if html_report:
            components.html(html_report, height=900, scrolling=True)
        else:
            st.info("HTML 리포트가 생성되지 않았습니다.")
    tab_idx += 1

# 타겟 달성현황
with tabs[tab_idx]:
    if db_skipped_count > 0:
        st.info(f"이미 저장된 데이터 {db_skipped_count}건 스킵 (중복 업로드)")

    is_cumulative = bool(kpi_cumulative and kpi_cumulative.get("by_platform"))
    basis_label = "월 누계 기준" if is_cumulative else "당일 기준"

    if target_summary and target_summary.get("total_target", 0) > 0:
        total_pct = target_summary.get("total_achievement_pct", 0)
        color = "#3f51b5" if total_pct >= 70 else "#f57c00"
        daily_total = kpi_total.get("total_sales", 0)
        cumulative_total = target_summary.get("total_actual", 0)
        daily_line = f"&nbsp;·&nbsp; 당일 매출: {daily_total:,}원" if is_cumulative else ""

        st.markdown(f"""
        <div style="background:#1e1e2e;border-radius:10px;padding:16px 20px;margin-bottom:16px;">
          <div style="font-size:12px;color:#718096;margin-bottom:4px;">전체 달성률 — {target_summary.get('month','')} ({basis_label})</div>
          <div style="font-size:28px;font-weight:700;color:{color};">{total_pct}%</div>
          <div style="font-size:12px;color:#4a5568;margin-top:2px;">
            월 누계: {cumulative_total:,} / {target_summary.get('total_target',0):,}원
            {daily_line}
            &nbsp;·&nbsp; 잔여 {target_summary.get('days_remaining',0)}일
            &nbsp;·&nbsp; 일평균 {target_summary.get('daily_required',0):,}원 필요
          </div>
        </div>
        """, unsafe_allow_html=True)
        st.progress(min(total_pct / 100, 1.0))

        st.markdown("**플랫폼별 달성률**")
        for pt in target_summary.get("by_platform", []):
            pct = pt.get("achievement_pct", 0)
            flag = "🟠" if pt.get("flag") == "low_achievement" else "🔵"
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.markdown(f"{flag} **{pt['platform']}**")
                st.progress(min(pct / 100, 1.0))
                st.caption(f"{pt.get('actual',0):,} / {pt.get('target',0):,}원 · 일평균 {pt.get('daily_required',0):,}원 필요")
            with col_b:
                color_pt = "#f57c00" if pct < 70 else "#3f51b5"
                st.markdown(f"<div style='font-size:22px;font-weight:700;color:{color_pt};text-align:right;padding-top:8px;'>{pct}%</div>", unsafe_allow_html=True)
    else:
        st.info("타겟이 설정되지 않았습니다. 이번 달 목표 매출을 입력하면 달성률을 확인할 수 있습니다.")

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

            if is_cumulative:
                total_actual = int(sum(r.get("total_revenue", 0) for r in kpi_cumulative["by_platform"]))
                platform_actual_map = {r["platform"]: int(r.get("total_revenue", 0)) for r in kpi_cumulative["by_platform"]}
            else:
                total_actual = kpi_total.get("total_sales", 0)
                platform_actual_map = {r["platform"]: r["total_sales"] for r in by_platform}

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

tab_idx += 1

# 이상치
if anomalies:
    with tabs[tab_idx]:
        for a in anomalies:
            severity = a.get("severity", "info")
            msg = a.get("message", "")
            if severity == "warning":
                st.warning(f"**[{a.get('type','').upper()}]** {msg}")
            else:
                st.info(f"**[{a.get('type','').upper()}]** {msg}")
    tab_idx += 1

# AI 코멘터리
if state.get("llm_commentary"):
    with tabs[tab_idx]:
        st.markdown(f"""
        <div style="background:#1e1e2e; border-left:3px solid #10b981;
                    border-radius:0 12px 12px 0; padding:20px 24px; margin-top:8px;">
            <div style="font-size:11px; color:#10b981; letter-spacing:0.8px;
                        text-transform:uppercase; margin-bottom:10px; font-weight:600;">
                AI 코멘터리 · GPT-4o-mini
            </div>
            <div style="font-size:14px; line-height:1.8; color:#cbd5e0;">{state['llm_commentary']}</div>
        </div>
        """, unsafe_allow_html=True)
    tab_idx += 1

# 다운로드
with tabs[tab_idx]:
    st.markdown("**리포트 다운로드**")
    col_d1, col_d2 = st.columns(2)

    with col_d1:
        html_report = state.get("html_report", "")
        if "html" in output_options and html_report:
            st.download_button(
                label="📧 HTML 리포트 다운로드",
                data=html_report.encode("utf-8"),
                file_name=f"sales_report_{report_date_raw}.html",
                mime="text/html",
                use_container_width=True,
            )

    with col_d2:
        excel_path = state.get("excel_path", "")
        if "excel" in output_options and excel_path and Path(excel_path).exists():
            with open(excel_path, "rb") as f:
                st.download_button(
                    label="📥 Excel 리포트 다운로드",
                    data=f.read(),
                    file_name=f"sales_report_{report_date_raw}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

    st.divider()
    st.markdown("**이메일 발송 상태**")
    if state.get("email_sent"):
        st.success("이메일이 성공적으로 발송되었습니다.")
    else:
        st.info(".env 파일에 EMAIL_SENDER, EMAIL_PASSWORD를 설정하면 자동 발송됩니다.")
