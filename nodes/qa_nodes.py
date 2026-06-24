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
[daily_kpi 테이블]
- report_date (TEXT, YYYY-MM-DD): 리포트 기준일
- channel (TEXT): 채널 구분
- platform (TEXT): 플랫폼/매장명 (HCC, HCC 부산점, HCC 제주점, 메이크샵, 네이버(주)(스토어팜), 주식회사 카카오)
- zor (INTEGER): 주문건수
- zre (INTEGER): 반품건수
- net_receipt (INTEGER): 순영수증 (ZOR-ZRE)
- hcc_revenue (REAL): HCC 매출
- helinox_revenue (REAL): 헬리녹스 매출
- total_revenue (REAL): 매출
- total_point (REAL): 포인트
- total_fee (REAL): 봉사료

[daily_product 테이블]
- report_date (TEXT, YYYY-MM-DD): 리포트 기준일
- product_code (TEXT): 제품코드
- product_name (TEXT): 제품명
- category_l1, category_l2, category_l3 (TEXT): 대/중/소분류
- qty (INTEGER): 판매수량
- revenue (REAL): 매출
- zre_qty (INTEGER): 반품건수
"""


def sql_guard(sql: str) -> tuple[bool, str]:
    sql_clean = sql.strip().rstrip(";")
    sql_upper = sql_clean.upper()

    if not sql_upper.startswith("SELECT"):
        return False, "SELECT 쿼리만 허용됩니다."

    for kw in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{kw}\b", sql_upper):
            return False, f"금지된 키워드: {kw}"

    referenced_tables = set(re.findall(r"\bFROM\s+(\w+)|\bJOIN\s+(\w+)", sql_upper))
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
        "- 날짜 비교는 report_date 컬럼 사용\n"
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
