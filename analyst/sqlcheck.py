"""Check and run the SQL a model wrote, before anyone reads its result.

The connection is already read-only; these checks add what read-only does not cover: one
statement, a query rather than a command, only the analysis tables, and a row cap. DuckDB's own
parser decides what the statement is, so a keyword hidden in a string or a comment cannot fool
the check the way a regular expression could.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import duckdb

from analyst.data import SCHEMA

MAX_ROWS = 200


class SQLRejected(ValueError):
    """The SQL is not a single read-only query over the analysis tables."""


@dataclass
class QueryResult:
    sql: str
    columns: list[str]
    rows: list[tuple]
    truncated: bool = False
    warnings: list[str] = field(default_factory=list)


def clean(sql: str) -> str:
    sql = sql.strip()
    if sql.startswith("```"):
        sql = sql.strip("`")
        sql = sql.removeprefix("sql").removeprefix("SQL")
    return sql.strip().rstrip(";").strip()


def check(con: duckdb.DuckDBPyConnection, sql: str) -> str:
    """Return the cleaned SQL, or raise SQLRejected with a message the model can act on."""
    sql = clean(sql)
    if not sql:
        raise SQLRejected("the SQL is empty")
    try:
        statements = con.extract_statements(sql)
    except duckdb.Error as exc:
        raise SQLRejected(f"the SQL does not parse: {exc}") from exc
    if len(statements) != 1:
        raise SQLRejected("write exactly one SQL statement")
    if statements[0].type != duckdb.StatementType.SELECT:
        raise SQLRejected("only SELECT queries are allowed")
    try:
        tables = con.get_table_names(sql)
    except duckdb.Error as exc:
        raise SQLRejected(f"the SQL does not parse: {exc}") from exc
    tree = con.execute("SELECT json_serialize_sql(?)", [sql]).fetchone()[0]
    if '"TABLE_FUNCTION"' in tree:
        raise SQLRejected(f"table functions are not allowed; query only {sorted(SCHEMA)}")
    unknown = sorted(t for t in tables if t.split(".")[-1] not in SCHEMA)
    if unknown:
        raise SQLRejected(f"unknown tables {unknown}; use only {sorted(SCHEMA)}")
    return sql


def run(con: duckdb.DuckDBPyConnection, sql: str) -> QueryResult:
    """Check, then execute with a row cap. Errors come back as SQLRejected with DuckDB's message."""
    sql = check(con, sql)
    try:
        cur = con.execute(f"SELECT * FROM ({sql}) AS q LIMIT {MAX_ROWS + 1}")
        rows = cur.fetchall()
        columns = [d[0] for d in cur.description]
    except duckdb.Error as exc:
        raise SQLRejected(f"the query failed: {str(exc).splitlines()[0]}") from exc
    result = QueryResult(sql=sql, columns=columns, rows=rows[:MAX_ROWS], truncated=len(rows) > MAX_ROWS)
    result.warnings = sanity(result)
    return result


def sanity(result: QueryResult) -> list[str]:
    """Cheap checks that catch a query that ran but answers nothing."""
    out = []
    if not result.rows:
        out.append("the query returned no rows")
    for i, name in enumerate(result.columns):
        values = [r[i] for r in result.rows]
        if values and all(v is None for v in values):
            out.append(f"column {name} is empty (all NULL)")
    if result.truncated:
        out.append(f"more than {MAX_ROWS} rows; only the first {MAX_ROWS} are used")
    return out
