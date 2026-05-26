ANOMALY_THRESHOLD_PCT = 30

ONLINE_PLATFORM_MAP = {
    "KCP(한국사이버결제)": "메이크샵",
    "네이버파이낸셜 주식회사": "메이크샵",
    "카카오페이": "메이크샵",
    "엔에이치엔페이코": "메이크샵",
    "비바리퍼블리카": "메이크샵",
}

OFFLINE_STORE_MAP = {
    "HCC": "서울",
    "HCC 부산점": "부산",
    "HCC 제주점": "제주",
}

CATEGORY_ALIAS = {"TRVR": "HCC"}
HELINOX_PRODUCT_KEYWORD = "DX1197_CLASSIC 8oz Mug"

VALID_ORDER_TYPES = ["ZOR", "ZRE"]
EXCLUDE_ORDER_TYPES = ["ZFD"]

MONTHLY_TARGETS = {
    "2025-05": {
        "_total": 50_000_000,
        "HCC": 20_000_000,
        "HCC 부산점": 10_000_000,
        "HCC 제주점": 8_000_000,
        "메이크샵": 12_000_000,
    },
    "2025-06": {
        "_total": 55_000_000,
        "HCC": 22_000_000,
        "HCC 부산점": 11_000_000,
        "HCC 제주점": 9_000_000,
        "메이크샵": 13_000_000,
    },
}

PROMOTIONS = {
    "2025-05": [
        {"name": "어버이날 프로모션", "start": "20250501", "end": "20250510"},
    ],
}

LLM_MODEL = "gpt-4o-mini"
LLM_MAX_TOKENS = 800
