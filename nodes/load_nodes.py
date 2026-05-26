import logging
import pandas as pd

logger = logging.getLogger(__name__)


def file_load_node(state: dict) -> dict:
    errors = list(state.get("errors", []))
    offline_df = pd.DataFrame()
    online_df = pd.DataFrame()

    offline_path = state.get("offline_path", "")
    if offline_path:
        try:
            offline_df = pd.read_excel(offline_path)
            logger.info(f"오프라인 파일 로드 완료: {len(offline_df)}행")
        except Exception as e:
            logger.warning(f"오프라인 파일 로드 실패: {e}")
            errors.append(f"오프라인 파일 로드 실패: {e}")
    else:
        errors.append("오프라인 파일 경로가 없습니다.")

    online_path = state.get("online_path", "")
    if online_path:
        try:
            online_df = pd.read_excel(online_path)
            logger.info(f"온라인 파일 로드 완료: {len(online_df)}행")
        except Exception as e:
            logger.warning(f"온라인 파일 로드 실패: {e}")
            errors.append(f"온라인 파일 로드 실패: {e}")

    return {**state, "offline_df": offline_df, "online_df": online_df, "errors": errors}
