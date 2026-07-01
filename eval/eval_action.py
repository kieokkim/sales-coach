"""
eval/eval_action.py
action_node의 출력이 구조적으로 충분히 구체적인지 판정한다
(Eval 2-A: Action 품질, rule-based).

LLM judge(Eval 2-B)는 별도 작업이며 여기서는 다루지 않는다.
"""
import logging

logger = logging.getLogger(__name__)

_VAGUE_PHRASES = ["검토가 필요", "확인이 필요", "고려해", "살펴봐야"]


def evaluate_actions(state: dict) -> dict:
    """
    state['actions'] 리스트를 받아 각 액션의 구조적 품질을 채점한다.

    채점 기준 (액션 1개당 최대 4점):
    - owner가 비어있지 않다: 1점
    - action 문장에 모호 표현이 없다: 1점
    - scope 필드가 존재한다: 1점
    - expected_impact 필드가 존재한다: 1점

    반환:
    {
        "action_count": int,
        "avg_score": float,  # 0~4
        "details": [{"timing":..., "score":..., "issues":[...]}]
    }
    """
    actions = state.get("actions", [])
    if not actions:
        return {"action_count": 0, "avg_score": 0.0, "details": []}

    details = []
    total_score = 0

    for a in actions:
        score = 0
        issues = []

        owner = a.get("owner", "").strip()
        if owner:
            score += 1
        else:
            issues.append("owner 없음")

        action_text = a.get("action", "")
        if not any(phrase in action_text for phrase in _VAGUE_PHRASES):
            score += 1
        else:
            issues.append("모호한 표현 포함")

        if a.get("scope", "").strip():
            score += 1
        else:
            issues.append("scope 없음")

        if a.get("expected_impact", "").strip():
            score += 1
        else:
            issues.append("expected_impact 없음")

        details.append({
            "timing": a.get("timing", ""),
            "score": score,
            "issues": issues,
        })
        total_score += score

    avg_score = round(total_score / len(actions), 2)

    return {
        "action_count": len(actions),
        "avg_score": avg_score,
        "details": details,
    }
