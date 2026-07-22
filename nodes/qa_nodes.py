import json
import logging
import os
import re

from config import LLM_MODEL
from db import get_db

logger = logging.getLogger(__name__)

ALLOWED_TABLES = {"daily_kpi", "daily_product"}
FORBIDDEN_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER",
    "CREATE", "ATTACH", "PRAGMA", "REPLACE", "TRUNCATE",
]


def get_schema_context() -> str:
    return """
[daily_kpi 테이블] — 채널/플랫폼별 일일 KPI (날짜당 여러 행 존재)
- report_date (TEXT, YYYY-MM-DD)
- platform (TEXT): HCC, HCC Store 1, HCC Store 2, 메이크샵, 네이버(주)(스토어팜), 주식회사 카카오
- net_receipt, total_revenue, total_point, total_fee (REAL/INTEGER)

[daily_product 테이블] — 제품별 일일 판매/반품 (날짜당 제품 수만큼 행 존재)
- report_date (TEXT, YYYY-MM-DD)
- product_code, product_name (TEXT)
- category_l1, category_l2, category_l3 (TEXT)
- qty (판매수량), revenue (매출), zre_qty (반품수량)

중요 규칙:
1. 두 테이블 모두 날짜당 여러 행이 존재합니다 (플랫폼별/제품별로 행이 나뉨).
   "전체 매출", "총 반품" 등 합계를 묻는 질문에는 반드시 SUM()을 사용하세요.
   SUM() 없이 조회하면 한 행만 반환되어 틀린 값이 됩니다.
2. 제품명(예: V.TARP, V.TAP)이 질문에 나오면 daily_product 테이블을 사용하세요.
   daily_kpi의 platform 컬럼에는 제품명이 들어가지 않습니다.
3. 반품 수량 컬럼명은 정확히 zre_qty 입니다 (zre가 아님).
4. 제품명은 LIKE로 부분 일치 검색하세요 (예: WHERE product_name LIKE '%V.TARP%').
   정확히 일치하는 표기를 모를 수 있기 때문입니다.
5. "이번달" 같은 기간 질문은 report_date LIKE 'YYYY-MM%' 형식을 사용하세요.
6. daily_product, daily_kpi 테이블은 모두 "날짜별 집계" 테이블입니다.
   거래(영수증) 단위 정보가 없으므로 아래 질문에는 SQL로 답할 수 없습니다:
   - "A를 사는 사람이 같이 사는 제품은?" (장바구니/연관구매)
   - "오늘 어떤 조합으로 많이 샀어?" (동시구매 패턴)
   - 특정 고객의 구매 이력 (고객 식별자 없음)
   이런 질문이 들어오면 SQL 대신 정확히 "NO_QUERY_POSSIBLE"라고만 응답하세요.
"""


def sql_guard(sql: str) -> tuple[bool, str]:
    sql_clean = sql.strip().rstrip(";")
    sql_upper = sql_clean.upper()
    # 탐지 전용 정규화본 — 큰따옴표/백틱/대괄호로 감싼 식별자가 \w+ 매칭을
    # 피해 FORBIDDEN_KEYWORDS·테이블명 검사를 우회하던 문제(Decision 32)를
    # 막는다. 실행되는 sql_clean(원본)은 안 건드림 — 탐지 로직만 영향.
    sql_detect = re.sub(r'["`\[\]]', "", sql_upper)

    if not sql_upper.startswith("SELECT"):
        return False, "SELECT 쿼리만 허용됩니다."

    for kw in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{kw}\b", sql_detect):
            return False, f"금지된 키워드: {kw}"

    referenced_tables = set(re.findall(r"\bFROM\s+(\w+)|\bJOIN\s+(\w+)", sql_detect))
    flat = {t for pair in referenced_tables for t in pair if t}
    disallowed = flat - {t.upper() for t in ALLOWED_TABLES}
    if disallowed:
        return False, f"허용되지 않은 테이블: {', '.join(disallowed)}"

    return True, sql_clean


def generate_sql(question: str, report_date: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return ""

    schema = get_schema_context()
    system_prompt = (
        "당신은 SQLite 쿼리 생성기입니다.\n"
        "사용자의 자연어 질문을 SQL SELECT 쿼리로 변환하세요.\n\n"
        f"{schema}\n\n"
        "규칙:\n"
        "- SELECT 쿼리만 작성하세요\n"
        "- 반드시 SQL만 출력하세요 (설명, 마크다운 코드블록 없이)\n"
        f"- '오늘', '이번달' 등은 기준일 {report_date}(YYYY-MM-DD)를 기준으로 해석하세요\n"
        "- 날짜 비교는 report_date 컬럼 사용\n\n"
        "예시:\n"
        "Q: 오늘 전체 매출 얼마야?\n"
        f"A: SELECT SUM(total_revenue) as total_revenue FROM daily_kpi WHERE report_date = '{report_date}'\n\n"
        "Q: 이번달 V.TARP 판매량은?\n"
        f"A: SELECT SUM(qty) as total_qty FROM daily_product WHERE report_date LIKE '{report_date[:7]}%' AND product_name LIKE '%V.TARP%'\n\n"
        "Q: 이번달 반품 수량은?\n"
        f"A: SELECT SUM(zre_qty) as total_zre FROM daily_product WHERE report_date LIKE '{report_date[:7]}%'\n"
    )

    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = ChatOpenAI(model=LLM_MODEL, max_tokens=300, api_key=api_key, temperature=0)
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=question),
    ])
    sql = response.content.strip()
    sql = sql.removeprefix("```sql").removeprefix("```").removesuffix("```").strip()

    if sql == "NO_QUERY_POSSIBLE":
        return "NO_QUERY_POSSIBLE"

    return sql


def execute_query(sql: str) -> list[dict]:
    try:
        with get_db() as conn:
            conn.row_factory = lambda cursor, row: {
                col[0]: row[i] for i, col in enumerate(cursor.description)
            }
            return conn.execute(sql).fetchall()
    except Exception as e:
        logger.warning(f"SQL 실행 실패: {e}")
        return []


def generate_answer(question: str, sql: str, rows: list[dict]) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return "API 키가 설정되지 않아 답변을 생성할 수 없습니다."

    if not rows:
        return "조회된 데이터가 없습니다."

    system_prompt = (
        "당신은 리테일 매출 데이터 분석 어시스턴트입니다.\n"
        "조회 결과를 바탕으로 사용자의 질문에 한국어로 답변하세요.\n"
        "금액은 억/만원 단위로 읽기 쉽게 표시하세요.\n"
        "데이터에 기반한 사실만 답변하세요.\n"
    )
    context = (
        f"질문: {question}\n"
        f"실행 SQL: {sql}\n"
        f"조회 결과 ({len(rows)}건):\n{json.dumps(rows[:50], ensure_ascii=False, default=str)}"
    )

    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = ChatOpenAI(model=LLM_MODEL, max_tokens=500, api_key=api_key, temperature=0)
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=context),
    ])
    return response.content.strip()


def answer_question(question: str, report_date: str) -> dict:
    result = {
        "question": question,
        "sql": "",
        "rows": [],
        "answer": "",
        "error": "",
    }

    try:
        sql = generate_sql(question, report_date)
        if not sql:
            result["error"] = "OPENAI_API_KEY가 설정되지 않았습니다."
            return result

        if sql == "NO_QUERY_POSSIBLE":
            result["answer"] = (
                "이 질문은 현재 저장된 데이터로는 답하기 어렵습니다. "
                "장바구니/연관구매 분석은 일일 리포트의 인사이트 카드에서 "
                "별도로 제공되고 있습니다 (거래 단위 원본 데이터가 DB에 저장되지 않음)."
            )
            return result

        valid, validated_sql = sql_guard(sql)
        if not valid:
            result["error"] = f"쿼리 검증 실패: {validated_sql}"
            logger.warning(f"SQL 검증 실패: {sql} → {validated_sql}")
            return result

        result["sql"] = validated_sql
        rows = execute_query(validated_sql)
        result["rows"] = rows
        result["answer"] = generate_answer(question, validated_sql, rows)

    except Exception as e:
        logger.warning(f"answer_question 실패: {e}")
        result["error"] = str(e)

    return result
