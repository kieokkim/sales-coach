ONLINE_PLATFORM_MAP = {
    "KCP(한국사이버결제)": "메이크샵",
    "네이버파이낸셜 주식회사": "메이크샵",
    "카카오페이": "메이크샵",
    "엔에이치엔페이코": "메이크샵",
    "비바리퍼블리카": "메이크샵",
}

OFFLINE_STORE_MAP = {
    "HCC": "서울",
    "HCC Store 1": "부산",
    "HCC Store 2": "제주",
}

CATEGORY_ALIAS = {"TRVR": "HCC"}
HELINOX_PRODUCT_KEYWORD = "DX1197_CLASSIC 8oz Mug"

VALID_ORDER_TYPES = ["ZOR", "ZRE"]
EXCLUDE_ORDER_TYPES = ["ZFD"]

MONTHLY_TARGETS = {
    "2025-04": {
        "_total": 4_500_000_000,
    },
    "2025-05": {
        "_total": 5_000_000_000,
        "HCC": 2_000_000_000,
        "HCC Store 1": 1_000_000_000,
        "HCC Store 2": 800_000_000,
        "메이크샵": 1_200_000_000,
    },
    "2025-06": {
        "_total": 5_500_000_000,
        "HCC": 2_200_000_000,
        "HCC Store 1": 1_100_000_000,
        "HCC Store 2": 900_000_000,
        "메이크샵": 1_300_000_000,
    },
}

PROMOTIONS = {
    "2025-05": [
        {"name": "어버이날 프로모션", "start": "20250501", "end": "20250510"},
    ],
}

LLM_MODEL = "gpt-4o-mini"
LLM_MAX_TOKENS = 1500

# ─────────────────────────────────────────────
# DOMAIN_PARAMS — 회사별로 조절하는 도메인 파라미터
# 구조(코드)는 universal, 이 값만 회사에 맞게 교체한다.
# config가 single source of truth. 각 값의 근거는 COMPANY_PROFILE.md에 서술.
# ─────────────────────────────────────────────
DOMAIN_PARAMS = {
    # 반품 이상 판정 = 유의성(Wilson) AND 효과크기(수량 하한 AND 금액 구간).
    # 건수 기준(예: 3건)은 제품 단가를 무시해 저가품 다건과 고가품 소량을
    # 동일 취급하는 문제가 있었다 — 금액 기준으로 전환.
    # 단일 문턱(예: 200만원)은 199만원 vs 200만원 같은 칼날 경계 문제가
    # 있어, 목표(target) severity와 동일하게 구간화(medium/high)했다.
    # 금액만으로는 극단적으로 낮은 baseline(평소 반품 0에 가까운 희귀
    # 고가품)에서 qty=1도 Wilson 유의성을 통과해 91일 중 27일 과다트리거가
    # 발생 — qty≥2 하한을 AND로 병행해 단발성 노이즈를 차단한다.
    # 91일 실측 반품금액 분포(90pct≈69만, 99pct≈252만) 기준 캘리브레이션.
    # 근거는 COMPANY_PROFILE.md.
    "return_min_qty": 2,               # 오늘 반품 수량 이 미만(=1)이면 금액 무관 배제
    "return_amount_medium": 700_000,   # qty≥return_min_qty AND 이 금액 이상이면 medium
    "return_amount_high": 2_000_000,   # qty≥return_min_qty AND 이 금액 이상이면 high
    "min_baseline_days": 14,  # 과거 기준선 최소 일수 (미만이면 평소값 불안정 → 판정 보류)
    "trend_z_threshold": 1.5, # 가속 z-score 이 값 이상 음(陰)으로 꺾이면 추세악화 후보
                              # (효과크기: 회사 변동성 대비 몇 시그마부터 유의)
    # 목표미달 판정 — daily_required 산식폭발 억제. 근거는 COMPANY_PROFILE.md.
    "target_daily_cap_multiplier": 1.5,  # daily_required 상한 = 이 배수 × (월목표/총일수).
                                         # 남은목표/잔여일이 월말 쌍곡선 발산하는 것 억제.
    "target_skip_last_days": 3,          # 잔여 이 값 이하 시 목표미달 판정 보류(최후 안전판).
    "target_low_achievement_pct": 70.0,  # 누적 달성률 이 % 미만이면 low_achievement 플래그.
    "target_shortfall_ratio_early": 0.8, # 잔여 ≥7일: net<조정목표×이 비율이면 미달로 판정.
    "target_shortfall_ratio_late": 0.6,  # 잔여 <7일: 월말 완화된 미달 문턱.
}


def classify_return_severity(qty: int, amount: float) -> str | None:
    """
    반품 수량+금액을 severity 구간으로 분류. 효과크기 미달이면 None.
    qty < return_min_qty(=1건)면 금액과 무관하게 배제 — 단발성 노이즈 차단.
    """
    if qty < DOMAIN_PARAMS.get("return_min_qty", 2):
        return None
    if amount >= DOMAIN_PARAMS.get("return_amount_high", 2_000_000):
        return "high"
    if amount >= DOMAIN_PARAMS.get("return_amount_medium", 700_000):
        return "medium"
    return None


# ─────────────────────────────────────────────
# 통계 표준 상수 — 도메인 무관 (회사 바뀌어도 불변)
# ─────────────────────────────────────────────
STAT_Z_95 = 1.96     # Wilson 95% 신뢰수준 z_{α/2} (통계 표준값, 도메인 문턱 아님)
