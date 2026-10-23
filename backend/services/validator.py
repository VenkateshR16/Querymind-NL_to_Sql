"""
SQL validation: blocks dangerous keywords, formats SQL, checks syntax.
"""
import re, sqlparse

BLOCKED = ['DROP','DELETE','INSERT','UPDATE','ALTER','CREATE','TRUNCATE',
           'EXEC','EXECUTE','GRANT','REVOKE','PRAGMA','ATTACH','DETACH']

def validate_sql(sql: str) -> dict:
    if not sql or not sql.strip():
        return {"valid": False, "error": "Empty SQL query"}

    sql_upper = sql.upper().strip()

    # Block dangerous keywords
    for kw in BLOCKED:
        if re.search(r'\b' + kw + r'\b', sql_upper):
            return {"valid": False, "error": f"Operation not allowed: {kw}"}

    # Must start with SELECT
    if not sql_upper.lstrip().startswith('SELECT') and not sql_upper.lstrip().startswith('WITH'):
        return {"valid": False, "error": "Only SELECT queries are allowed"}

    # Check balanced parentheses
    if sql.count('(') != sql.count(')'):
        return {"valid": False, "error": "Unbalanced parentheses in query"}

    # Format
    try:
        formatted = sqlparse.format(
            sql, reindent=True, keyword_case='upper',
            identifier_case='lower', strip_comments=True
        )
        return {"valid": True, "formatted": formatted, "original": sql}
    except Exception as e:
        return {"valid": True, "formatted": sql, "original": sql}
