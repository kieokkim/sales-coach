"""
eval/eval_insight.py
Eval 1: insight_node의 top_issues category 집합과 ground_truth 카테고리
집합을 비교한다. 키워드 매칭을 폐기하고 집합 비교로 전환 —
프롬프트가 "편중 언급 금지"인데 채점기가 "편중 단어 요구"하던 자기모순 해소.

정상날(양쪽 다 빈 집합)은 PASS.
LLM이 기준 미달인데 태깅한 경우(false positive)는 정밀도 하락으로 감점.
"""
import logging

logger = logging.getLogger(__name__)

_VALID_CATEGORIES = {"반품이슈", "수익성문제", "목표미달", "추세악화", "편중", "기타"}


def evaluate_insight(state: dict, ground_truth_set: dict) -> dict:
    """
    반환:
    {
        "match": bool,               # 완전 일치 여부 (집합 동일)
        "precision": float,          # 맞게 태깅한 비율
        "recall": float,             # 잡아야 할 걸 잡은 비율
        "f1": float,
        "predicted": set,            # LLM이 태깅한 카테고리
        "ground_truth": set,         # 정답 카테고리
        "false_positives": set,      # LLM이 잘못 넣은 것 (0401 케이스)
        "false_negatives": set,      # LLM이 놓친 것
    }
    """
    insights = state.get("insights", {})
    top_issues = insights.get("top_issues", [])

    # LLM이 태깅한 카테고리 집합 (편중은 정상적으로 제외되어야 하나, 들어오면 집합에서 뺌)
    predicted = set()
    for item in top_issues:
        if isinstance(item, dict):
            cat = item.get("category", "")
            if cat in _VALID_CATEGORIES and cat != "편중":
                predicted.add(cat)

    gt = ground_truth_set.get("categories", set())

    # 집합 비교
    true_positives = predicted & gt
    false_positives = predicted - gt
    false_negatives = gt - predicted

    # 정상날 처리: 양쪽 다 빈 집합이면 완전 일치
    if not predicted and not gt:
        return {
            "match": True, "precision": 1.0, "recall": 1.0, "f1": 1.0,
            "predicted": predicted, "ground_truth": gt,
            "false_positives": set(), "false_negatives": set(),
        }

    precision = (
        len(true_positives) / len(predicted) if predicted else 0.0
    )
    recall = (
        len(true_positives) / len(gt) if gt else 0.0
    )
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0 else 0.0
    )

    return {
        "match": predicted == gt,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "predicted": predicted,
        "ground_truth": gt,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
    }
