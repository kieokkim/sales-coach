"""
eval/eval_insight.py
insight_node가 도출한 top_issue가 ground_truth의 category와
같은 방향을 가리키는지 판정한다 (Eval 1: Insight 정확도).

판정은 정확한 문자열 일치가 아니라 카테고리 키워드 포함 여부로 한다.
insight_node.top_issue는 자유 서술 문장이므로 완전 일치를 요구하면
정상적으로 맞춘 케이스도 FAIL로 잘못 판정될 수 있다.
"""
import logging

logger = logging.getLogger(__name__)

_CATEGORY_KEYWORDS = {
    "반품이슈": ["반품", "품질", "리콜"],
    "목표미달": ["목표", "달성률", "미달", "부진", "일별", "순매출"],
    "수익성문제": ["마진", "수익성", "할인"],
    "추세악화": ["하락", "가속", "추세", "악화"],
    "편중": ["편중", "집중", "비중"],
    "정상": [],
}


def evaluate_insight(state: dict, ground_truth: dict) -> dict:
    """
    state['insights']['top_issue']와 ground_truth['category']를 비교한다.

    반환:
    {
        "match": bool,
        "ground_truth_category": str,
        "predicted_top_issue": str,
        "ground_truth_severity": str,
    }
    """
    insights = state.get("insights", {})
    top_issue = insights.get("top_issue", "") or ""

    gt_category = ground_truth.get("category", "정상")
    gt_severity = ground_truth.get("severity", "none")

    if gt_category == "정상":
        # 이슈가 없는 날: insight가 critical한 issue를 만들어내지 않았으면 PASS로 간주
        keywords_other = [
            kw for cat, kws in _CATEGORY_KEYWORDS.items()
            if cat != "정상" for kw in kws
        ]
        false_alarm = any(kw in top_issue for kw in keywords_other)
        return {
            "match": not false_alarm,
            "ground_truth_category": gt_category,
            "predicted_top_issue": top_issue,
            "ground_truth_severity": gt_severity,
        }

    keywords = _CATEGORY_KEYWORDS.get(gt_category, [])
    matched = any(kw in top_issue for kw in keywords)

    return {
        "match": matched,
        "ground_truth_category": gt_category,
        "predicted_top_issue": top_issue,
        "ground_truth_severity": gt_severity,
    }
