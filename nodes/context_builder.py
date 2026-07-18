"""
nodes/context_builder.py
patterns 딕셔너리 → context 문자열 변환 공통 모듈.
insight_node와 commentary_nodes가 공유한다.
새 patterns 키를 추가할 때는 이 파일 하나만 수정하면 된다.
PERSONA.md 참조 — 타겟 사용자 기준으로 어조/깊이 결정.
"""
import logging

from config import DOMAIN_PARAMS

logger = logging.getLogger(__name__)


def build_patterns_context(state: dict) -> str:
    patterns = state.get("patterns", {})
    kpi_total = state.get("kpi_total", {})
    kpi_summary = state.get("kpi_summary", {})
    target_summary = state.get("target_summary", {})
    anomalies = state.get("anomalies", [])
    insights = state.get("insights", {})
    actions = state.get("actions", [])
    report_date = state.get("report_date", "")

    rd = (f"{report_date[:4]}-{report_date[4:6]}-{report_date[6:8]}"
          if len(report_date) >= 8 else report_date)

    lines = [f"[기준일: {rd}]", ""]

    if kpi_total:
        lines.append("[오늘 전체 KPI]")
        lines.append(f"  총매출: {kpi_total.get('total_sales', 0):,}원")
        lines.append(f"  순영수증: {kpi_total.get('net_receipt', 0)}건")
        lines.append(f"  포인트: {kpi_total.get('total_point', 0):,}P")
        lines.append("")

    by_platform = kpi_summary.get("by_platform", [])
    if by_platform:
        lines.append("[플랫폼별 매출]")
        for rec in by_platform:
            lines.append(
                f"  {rec['platform']}: {rec['total_sales']:,}원 "
                f"(ZOR {rec['zor']}건, ZRE {rec['zre']}건)"
            )
        lines.append("")

    trends = patterns.get("channel_trends", [])
    if trends:
        lines.append("[채널 추세 — 오늘 vs 7일 평균]")
        for t in trends:
            lines.append(
                f"  {t['channel']}: 오늘 {t['today']:,}원 / "
                f"7일 평균 {t['seven_day_avg']:,}원 / "
                f"변화율 {t['change_pct']:+.1f}% ({t['flag']})"
            )
        lines.append("")

    trend_30d = patterns.get("trend_direction_30d", {})
    if trend_30d:
        lines.append("[30일 장기 추세]")
        lines.append(
            f"  전체: {trend_30d.get('overall_direction', '')} "
            f"({trend_30d.get('overall_change_pct', 0):+.1f}%, "
            f"{trend_30d.get('days_analyzed', 0)}일 분석)"
        )
        if trend_30d.get("acceleration") not in ("", "데이터부족"):
            lines.append(
                f"  가속도: {trend_30d.get('acceleration', '')} "
                f"({trend_30d.get('acceleration_pct', 0):+.1f}%)"
            )
        for ch, info in trend_30d.get("channel_trends", {}).items():
            lines.append(
                f"  {ch}: {info['direction']} ({info['change_pct']:+.1f}%)"
            )
        # 추세악화 게이트 — ground_truth와 동일 조건(방향 하락 AND 가속 z 유의).
        # 상승/횡보 중 단기 가속하락(0518류)은 여기서 걸러져 표시 안 됨.
        z_thr = DOMAIN_PARAMS.get("trend_z_threshold", 1.5)
        accel_z = trend_30d.get("accel_zscore")
        if (trend_30d.get("overall_direction") == "하락"
                and accel_z is not None and accel_z <= -z_thr):
            lines.append(
                f"  ⚠ 추세악화 신호: 30일 하락 + 최근 가속 z={accel_z:.2f} "
                f"(회사 변동성 {z_thr}σ 이상 음)"
            )
        lines.append("")

    movers = patterns.get("category_movers", [])
    if movers:
        lines.append("[카테고리별 매출 비중]")
        for m in movers[:5]:
            flag_str = " (구조적 집중, 장기 패턴)" if m["flag"] else ""
            lines.append(
                f"  {m['category_l1']}: {m['total_sales']:,}원 "
                f"({m['share_pct']}%){flag_str}"
            )
        lines.append("")

    returns = patterns.get("return_anomalies", [])
    if returns:
        lines.append("[반품 이상 — 평균 대비 3배 초과 제품]")
        for r in returns:
            lines.append(
                f"  {r['product_name']}: "
                f"오늘 {r['return_rate_today']:.1%} / "
                f"30일 평균 {r['return_rate_avg']:.1%} / "
                f"평균의 {r['multiplier']}배"
            )
        breakdown = patterns.get("return_reason_breakdown", {})
        if breakdown:
            lines.append("  사유별 금액:")
            for reason, amt in breakdown.items():
                if amt:
                    lines.append(f"    {reason}: {amt:,}원")
        lines.append("")
    else:
        lines.append("[반품 이상] 해당 없음")
        lines.append("")

    fc = patterns.get("forecast", {})
    if fc:
        lines.append("[월말 예측]")
        lines.append(f"  이번달 현재 누적: {fc.get('current_total', 0):,}원")
        lines.append(
            f"  일평균: {fc.get('daily_avg', 0):,}원 / "
            f"잔여 {fc.get('days_remaining', 0)}일"
        )
        lines.append(f"  예상 월말 매출: {fc.get('forecast_total', 0):,}원")
        lines.append(
            f"  월 목표: {fc.get('target', 0):,}원 / "
            f"예상 달성률: {fc.get('forecast_achievement_pct', 0)}%"
        )
        lines.append("")

    adt = patterns.get("adjusted_daily_target", {})
    if adt:
        lines.append("[조정 일별 목표 (요일/프로모션 보정)]")
        lines.append(
            f"  오늘 순매출: {adt.get('today_net_sales', 0):,}원"
        )
        lines.append(
            f"  조정 일별 목표: {adt.get('adjusted_daily_required', 0):,}원 "
            f"(기본: {adt.get('raw_daily_required', 0):,}원)"
        )
        lines.append(
            f"  달성률: {adt.get('achievement_vs_adjusted', 0)}% "
            f"/ 심각도: {adt.get('severity', 'none')}"
        )
        if adt.get("adjustments_applied"):
            lines.append(
                f"  적용된 보정: {', '.join(adt['adjustments_applied'])}"
            )
        lines.append("")

    if target_summary:
        lines.append("[타겟 달성 현황]")
        lines.append(
            f"  전체: {target_summary.get('total_achievement_pct', 0)}% 달성 "
            f"({target_summary.get('total_actual', 0):,} / "
            f"{target_summary.get('total_target', 0):,}원), "
            f"잔여 {target_summary.get('days_remaining', 0)}일"
        )
        for pt in target_summary.get("by_platform", []):
            lines.append(
                f"  {pt['platform']}: {pt['achievement_pct']}% (월 누적, 참고용) / "
                f"일평균 {pt['daily_required']:,}원 필요"
            )
        lines.append("")

    promo = patterns.get("promo_effect", {})
    if promo.get("active"):
        lines.append(
            f"[진행중 프로모션] {promo.get('name')}: "
            f"매출 리프트 {promo.get('sales_lift_pct', 0):+.1f}%"
        )
        lines.append("")

    if anomalies:
        lines.append("[이상치 감지]")
        for a in anomalies:
            lines.append(
                f"  [{a.get('severity', '').upper()}] {a.get('message', '')}"
            )
        lines.append("")

    combo = patterns.get("purchase_combo", {})
    if combo:
        lines.append("[동시구매 패턴]")
        lines.append(
            f"  전체 거래 {combo.get('total_orders', 0)}건 중 "
            f"교차구매(Helinox+HCC) {combo.get('cross_brand_orders', 0)}건 "
            f"({combo.get('cross_brand_pct', 0)}%)"
        )
        for c in combo.get("top_category_combos", [])[:3]:
            lines.append(f"  자주 같이 사는 조합: {c['pair']} ({c['count']}건)")
        lines.append("")

    basket = patterns.get("basket_metrics", {})
    if basket:
        lines.append("[채널별 구매 행동]")
        for channel, m in basket.items():
            lines.append(
                f"  {channel}: 거래당 평균 {m.get('avg_items_per_order', 0)}개 "
                f"/ {m.get('avg_amount_per_order', 0):,}원"
            )
        lines.append("")

    time_p = patterns.get("time_pattern", {})
    if time_p:
        lines.append("[요일 패턴]")
        lines.append(
            f"  오늘은 {time_p.get('today_weekday', '')}요일 "
            f"({'주말' if time_p.get('is_weekend') else '평일'})"
        )
        if time_p.get("today_weekday_avg"):
            lines.append(
                f"  {time_p.get('today_weekday', '')}요일 30일 평균: "
                f"{time_p.get('today_weekday_avg', 0):,}원"
            )
        lines.append("")

    assoc = patterns.get("basket_association", [])
    if assoc:
        lines.append("[장바구니 연관 분석]")
        for a in assoc[:3]:
            lines.append(
                f"  {a['item_a']} → {a['item_b']}: "
                f"동시구매 {a['co_occur_count']}건 "
                f"(신뢰도 {a['confidence']:.1%})"
            )
        lines.append("")

    discount = patterns.get("discount_sensitivity", {})
    if discount.get("bucket_summary"):
        lines.append("[할인율별 판매 + 마진 현황]")
        lines.append(
            f"  오늘 전체 마진율: {discount.get('margin_pct_overall', 0)}% "
            f"(마진 총액 {discount.get('total_margin', 0):,}원)"
        )
        if discount.get("theoretical_margin_pct") is not None:
            lines.append(
                f"  오늘 믹스 기대 마진: {discount.get('theoretical_margin_pct')}% / "
                f"실제 마진: {discount.get('margin_pct_overall')}% / "
                f"편차: {discount.get('margin_deviation')}%p"
            )
        for bucket, m in discount["bucket_summary"].items():
            lines.append(
                f"  할인 {bucket}: 제품 {m['product_count']}개, "
                f"평균 판매량 {m['avg_qty']}개"
            )
        top = discount.get("top_discounted", [])
        if top:
            lines.append("  최대 할인 제품 TOP3 (마진율 포함):")
            for t in top[:3]:
                lines.append(
                    f"    {t['product_name']}: {t['discount_pct']}% 할인, "
                    f"마진율 {t['margin_pct']}%, {t['qty']}개 판매"
                )
        lines.append("")

    if insights:
        lines.append("[AI 인사이트 분석]")
        top_issues = insights.get("top_issues", [])
        if top_issues:
            lines.append(f"  오늘 주목 이슈 ({len(top_issues)}개):")
            for it in top_issues:
                lines.append(f"    - [{it.get('category', '')}] {it.get('issue', '')}")
            if insights.get("relation") == "linked":
                lines.append("    (두 이슈는 연결됨 — 한쪽이 다른 쪽의 원인)")
            elif insights.get("relation") == "independent":
                lines.append("    (두 이슈는 독립적 — 원인이 서로 다름)")
        else:
            lines.append("  오늘 주목 이슈: 특이사항 없음 (정상 범위)")
        if insights.get("forecast_summary"):
            lines.append(f"  월말 예측: {insights['forecast_summary']}")
        if insights.get("trend_summary"):
            lines.append(f"  주목 추세: {insights['trend_summary']}")
        for r in insights.get("risk_items", []):
            lines.append(f"  ⚠️ 리스크: {r}")
        for o in insights.get("opportunity_items", []):
            lines.append(f"  ✅ 기회: {o}")
        lines.append("")

    by_product = kpi_summary.get("by_product", [])
    return_only = [p for p in by_product
                   if p["total_sales"] == 0 and p["zre_qty"] > 0]
    if return_only:
        lines.append("[오늘 반품만 발생한 제품 — 즉각 확인 필요]")
        for p in return_only:
            lines.append(
                f"  {p['product_name']}: 반품 {p['zre_qty']}개 "
                f"(오늘 신규 판매 없음, 이전 구매 반품 집중)"
            )
        lines.append("")

    if actions:
        lines.append("[권장 액션]")
        for a in actions:
            lines.append(
                f"  [{a.get('timing', '')}] {a.get('owner', '')}: "
                f"{a.get('action', '')}"
            )
            if a.get("scope"):
                lines.append(f"    범위: {a['scope']}")
            if a.get("expected_impact"):
                lines.append(f"    기대효과: {a['expected_impact']}")
        lines.append("")

    return "\n".join(lines)
