import os


def get_bool_env(name: str, default: bool = False) -> bool:
    """환경변수를 안전하게 참/거짓으로 파싱. "true"/"1"/"yes"(대소문자 무관)만 참,
    값이 없으면 default. 그 외 문자열은 거짓(오탈자로 데모모드가 몰래 켜지는
    사고보다, 몰래 꺼지는 쪽이 안전)."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("true", "1", "yes")


def is_demo_mode() -> bool:
    return get_bool_env("DEMO_MODE", default=False)
