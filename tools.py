import re
import threading

import duckdb

FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|copy|export|attach|detach|"
    r"install|load|pragma|call|set|vacuum|checkpoint)\b",
    re.IGNORECASE,
)
ALLOWED_START = re.compile(r"^\s*(with|select)\b", re.IGNORECASE)

SCHEMA_ERROR = re.compile(
    r"(catalog error|does not exist|does not have a column|binder error|referenced column|unknown)",
    re.IGNORECASE,
)


def validate(sql: str):
    body = sql.strip().rstrip(";")
    if not body:
        return "empty query"
    if ";" in body:
        return "multiple statements are not allowed"
    if not ALLOWED_START.match(body):
        return "query must start with SELECT or WITH"
    if FORBIDDEN.search(body):
        return "forbidden keyword in query"
    return None


def unescape_literal_backslashes(sql: str) -> str:
    return sql.replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r")


def run_sql(con: duckdb.DuckDBPyConnection, sql: str, timeout_s: float = 5.0, row_cap=None):
    sql = unescape_literal_backslashes(sql)
    error = validate(sql)
    if error:
        return {"ok": False, "error": error, "error_kind": "validation"}

    result = {}

    def worker():
        try:
            cur = con.cursor()
            rel = cur.execute(sql)
            if row_cap is None:
                rows = rel.fetchall()
                truncated = False
            else:
                rows = rel.fetchmany(row_cap + 1)
                truncated = len(rows) > row_cap
                rows = rows[:row_cap]
            result["columns"] = [d[0] for d in cur.description]
            result["rows"] = rows
            result["truncated"] = truncated
        except Exception as e:
            result["error"] = str(e)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout_s)
    if t.is_alive():
        con.interrupt()
        t.join(1.0)
        return {"ok": False, "error": f"timeout after {timeout_s}s", "error_kind": "timeout"}

    if "error" in result:
        kind = "schema" if SCHEMA_ERROR.search(result["error"]) else "runtime"
        return {"ok": False, "error": result["error"], "error_kind": kind}

    return {"ok": True, "columns": result["columns"], "rows": result["rows"],
            "truncated": result["truncated"]}


def format_for_model(result: dict, max_chars: int = 2000) -> str:
    if not result["ok"]:
        return f"ERROR ({result['error_kind']}): {result['error']}"
    cols = result["columns"]
    rows = result["rows"]
    lines = [", ".join(cols)]
    for r in rows:
        lines.append(", ".join(str(v) for v in r))
    if result["truncated"]:
        lines.append(f"... (truncated, showing first {len(rows)} rows)")
    else:
        lines.append(f"({len(rows)} rows)")
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n... (output truncated)"
    return text


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_sql",
            "description": ("Execute a read-only SELECT/WITH query against the database to "
                            "explore the data before writing rules. Use it to inspect value "
                            "distributions, sample rows, or check for anomalies."),
            "parameters": {
                "type": "object",
                "properties": {"sql": {"type": "string", "description": "A single SELECT or WITH query."}},
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_rules",
            "description": ("Submit the final set of data quality rules. Call this exactly once, "
                            "as your last action, once you are done exploring."),
            "parameters": {
                "type": "object",
                "properties": {
                    "rules": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "table": {"type": "string",
                                         "description": "Name of one of the 30 tables in the schema above."},
                                "dimension": {"type": "string",
                                             "description": "Data quality dimension, e.g. completeness, validity, "
                                                            "uniqueness, consistency, accuracy, referential_integrity."},
                                "description": {"type": "string"},
                                "sql": {"type": "string",
                                       "description": "A SELECT whose first column is the primary key of the "
                                                      "violating row in `table`."},
                            },
                            "required": ["table", "dimension", "description", "sql"],
                        },
                    }
                },
                "required": ["rules"],
            },
        },
    },
]
