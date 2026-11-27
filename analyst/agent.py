"""From a business question to a decision memo, in five steps:

1. Name the decision   the model states the decision the question serves and the metric.
2. Trust the data      the model writes SQL; code checks it, runs it read-only and checks the result.
3. Show the work       the memo carries the SQL and the rows it is based on.
4. Read the trend      code, not the model, reads a monthly series and leaves partial months out.
5. Make it last        every number in the memo must exist in the result, and the eval reruns
                       known questions on every change.

The model is asked for JSON with a fixed schema at each step. When SQL fails a check or does
not run, the error goes back to the model, up to MAX_SQL_TRIES times. When the memo uses a
number the result does not contain, the model gets one chance to fix it; after that the memo
is marked as unverified instead of being shown as if it were fine.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

import duckdb

from analyst.checks import Grounding, Trend, fmt, grounding, misattributed, trend
from analyst.data import COVERAGE, schema_text
from analyst.llm import ChatModel
from analyst.sqlcheck import QueryResult, SQLRejected, run

MAX_SQL_TRIES = 3
TABLE_ROWS_IN_PROMPT = 40

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"type": "string"},
        "metric": {"type": "string"},
        "sql": {"type": "string"},
    },
    "required": ["decision", "metric", "sql"],
}
SQL_SCHEMA = {"type": "object", "properties": {"sql": {"type": "string"}}, "required": ["sql"]}
MEMO_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "recommendation": {"type": "string"},
        "caveats": {"type": "string"},
    },
    "required": ["answer", "recommendation", "caveats"],
}

SYSTEM = f"""You are a data analyst at Olist, a Brazilian e-commerce marketplace. You answer
business questions with DuckDB SQL over these tables and nothing else:

{schema_text()}

Rules for SQL:
- One SELECT statement (WITH is fine). Only the tables above.
- Give every computed column a short snake_case alias.
- Rates as fractions between 0 and 1 (e.g. avg(is_late::INTEGER)), rounded to 4 decimals.
- Money and averages rounded to 2 decimals.
- Filter by date only when the question names a period or asks for a monthly trend; monthly
  trends group by purchase_month and keep 2017-01-01 to 2018-08-01.
- Aliases must not be SQL keywords (do, to, as, by, on, in, end); use descriptive names.
- Order the rows so the most important come first, and LIMIT long rankings to 10 rows.
"""

MEMO_RULES = """Write a short decision memo as JSON with three fields:
- answer: two or three sentences that answer the question with the key numbers.
- recommendation: one or two sentences on what to do, tied to the decision.
- caveats: one sentence on what the data cannot show.
Use only numbers that appear in the result table or the trend line, written as digits
(no "k" or "million"). Rates in the table are fractions: 0.0812 means 8.12%, not 81.2%.
Do not add up, average or invent numbers that are not in the table."""


@dataclass
class Memo:
    question: str
    decision: str = ""
    metric: str = ""
    sql: str = ""
    columns: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)
    attempts: list[dict[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    trend: str | None = None
    answer: str = ""
    recommendation: str = ""
    caveats: str = ""
    grounded: bool = False
    unsupported_numbers: list[str] = field(default_factory=list)
    misattributed_numbers: list[str] = field(default_factory=list)
    numbers_checked: int = 0
    failed: str | None = None
    model: str = ""
    llm_calls: int = 0

    def to_dict(self) -> dict[str, Any]:
        return json.loads(json.dumps(asdict(self), default=str))

    def markdown(self) -> str:
        if self.failed:
            return f"# {self.question}\n\n**No memo:** {self.failed}\n"
        head = "| " + " | ".join(self.columns) + " |\n|" + "---|" * len(self.columns) + "\n"
        body = "".join("| " + " | ".join(_cell(v) for v in r) + " |\n" for r in self.rows[:20])
        more = f"\n_{len(self.rows) - 20} more rows not shown._\n" if len(self.rows) > 20 else ""
        missing = ", ".join(self.unsupported_numbers)
        wrong_row = ", ".join(self.misattributed_numbers)
        status = ("All numbers in this memo were found in the query result, each next to its own "
                  "row where the memo names one.")  # fmt: skip
        if not self.grounded:
            parts = []
            if missing:
                parts.append(f"these numbers are not in the query result: {missing}")
            if wrong_row:
                parts.append(f"these numbers belong to another row than the one named: {wrong_row}")
            status = f"**Unverified:** {'; '.join(parts) or 'no answer'}."
        checks = [f"SQL passed the read-only checks and ran ({len(self.rows)} rows, "
                  f"{len(self.attempts)} attempt{'s' if len(self.attempts) != 1 else ''})."]  # fmt: skip
        checks += [f"Warning: {w}." for w in self.warnings]
        checks.append(status)
        trend_line = f"\n## Trend\n\n{self.trend}\n" if self.trend else ""
        return f"""# {self.question}

**Decision:** {self.decision}
**Metric:** {self.metric}

## Answer

{self.answer}

## Recommendation

{self.recommendation}
{trend_line}
## Evidence

```sql
{self.sql}
```

{head}{body}{more}
## Checks

{chr(10).join("- " + c for c in checks)}

## Caveats

{self.caveats} {COVERAGE}
"""


def _cell(v: Any) -> str:
    if isinstance(v, float):
        return fmt(v)
    return str(v)


def _table_for_prompt(result: QueryResult) -> str:
    lines = [" | ".join(result.columns)]
    lines += [" | ".join(_cell(v) for v in r) for r in result.rows[:TABLE_ROWS_IN_PROMPT]]
    if len(result.rows) > TABLE_ROWS_IN_PROMPT:
        lines.append(f"... {len(result.rows) - TABLE_ROWS_IN_PROMPT} more rows")
    return "\n".join(lines)


class Analyst:
    def __init__(self, model: ChatModel, con: duckdb.DuckDBPyConnection) -> None:
        self.model = model
        self.con = con

    def _ask(self, memo: Memo, messages: list[dict], schema: dict) -> dict[str, Any]:
        memo.llm_calls += 1
        reply = self.model.chat(messages, schema=schema)
        try:
            data = json.loads(reply.content)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def query(self, question: str) -> tuple[Memo, QueryResult | None, list[dict]]:
        """Steps 1 and 2: plan, write SQL, check and run it, retrying on errors."""
        memo = Memo(question=question, model=getattr(self.model, "name", ""))
        messages: list[dict] = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Question: {question}\n\nReply with JSON: the business decision "
             "this question serves, the metric that answers it, and the SQL."},
        ]  # fmt: skip
        plan = self._ask(memo, messages, PLAN_SCHEMA)
        memo.decision = str(plan.get("decision", "")).strip()
        memo.metric = str(plan.get("metric", "")).strip()
        sql = str(plan.get("sql", ""))
        messages.append({"role": "assistant", "content": json.dumps(plan)})
        for attempt in range(1, MAX_SQL_TRIES + 1):
            try:
                result = run(self.con, sql)
            except SQLRejected as exc:
                memo.attempts.append({"sql": sql, "error": str(exc)})
                if attempt == MAX_SQL_TRIES:
                    memo.failed = f"no valid SQL after {MAX_SQL_TRIES} attempts; last error: {exc}"
                    return memo, None, messages
                messages.append({"role": "user", "content": f"That SQL was rejected: {exc}. "
                                 "Fix it and reply with JSON containing only the corrected sql."})  # fmt: skip
                fixed = self._ask(memo, messages, SQL_SCHEMA)
                sql = str(fixed.get("sql", ""))
                messages.append({"role": "assistant", "content": json.dumps(fixed)})
                continue
            memo.attempts.append({"sql": result.sql, "error": ""})
            memo.sql = result.sql
            memo.columns = result.columns
            memo.rows = [list(r) for r in result.rows]
            memo.warnings = list(result.warnings)
            return memo, result, messages
        raise AssertionError("unreachable")

    def ask(self, question: str) -> Memo:
        memo, result, messages = self.query(question)
        if result is None:
            return memo
        t: Trend | None = trend(result)
        memo.trend = t.sentence() if t else None
        if t and t.excluded_partial:
            memo.warnings.append(f"{t.excluded_partial} partial months left out of the trend")
        trend_text = f"\nTrend computed by code: {memo.trend}" if memo.trend else ""
        warn_text = f"\nWarnings from the checks: {'; '.join(memo.warnings)}" if memo.warnings else ""
        messages.append({"role": "user", "content": f"Result of the SQL:\n{_table_for_prompt(result)}"
                         f"{trend_text}{warn_text}\n\n{MEMO_RULES}"})  # fmt: skip
        # The question, the SQL, the trend line and the coverage note may also supply numbers (years, limits).
        context = " ".join([question, result.sql, memo.trend or "", COVERAGE])
        for attempt in (1, 2):
            data = self._ask(memo, messages, MEMO_SCHEMA)
            memo.answer = str(data.get("answer", "")).strip()
            memo.recommendation = str(data.get("recommendation", "")).strip()
            memo.caveats = str(data.get("caveats", "")).strip()
            text = " ".join([memo.answer, memo.recommendation, memo.caveats])
            g: Grounding = grounding(text, result, context)
            memo.numbers_checked = g.checked
            memo.unsupported_numbers = g.unsupported
            stated = " ".join([memo.answer, memo.recommendation])
            memo.misattributed_numbers = misattributed(stated, result)
            memo.grounded = g.ok and not memo.misattributed_numbers and bool(memo.answer)
            if memo.grounded or attempt == 2:
                break
            problems = []
            if g.unsupported:
                problems.append(f"These numbers are not in the result: {', '.join(g.unsupported)}.")
            if memo.misattributed_numbers:
                problems.append("These numbers are next to the wrong row (number (row named)): "
                                f"{', '.join(memo.misattributed_numbers)}.")  # fmt: skip
            messages.append({"role": "assistant", "content": json.dumps(data)})
            problems.append("Rewrite the memo using only numbers from the result table or the trend line, "
                            "each with its own row.")  # fmt: skip
            messages.append({"role": "user", "content": " ".join(problems)})
        return memo
