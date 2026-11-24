"""Execution accuracy: does the agent's result hold the same answer as the reference SQL?

Column names and extra columns do not matter. Each reference column (or the ones listed in
"match") must appear among the agent's columns with the same values: in the same order when
the question asks for a ranking ("ordered"), as a multiset otherwise. Numbers match within 1%
(or 0.001), and a rate given as a percentage (x100) matches the fraction.
"""

from __future__ import annotations

import datetime as dt
from typing import Any


def _norm(v: Any) -> Any:
    if v is None or isinstance(v, bool):
        return v
    if isinstance(v, int | float):
        return float(v)
    if isinstance(v, dt.datetime):
        return v.date().isoformat()
    if isinstance(v, dt.date):
        return v.isoformat()
    try:
        return float(v)
    except (TypeError, ValueError):
        return str(v).strip().lower()


def _same(a: Any, b: Any, scale: float = 1.0) -> bool:
    if isinstance(a, float) and isinstance(b, float):
        b = b * scale
        return abs(a - b) <= max(0.001, 0.01 * abs(b))
    if isinstance(a, str) and isinstance(b, str) and len(a) >= 7 and len(b) >= 7 and a[4] == b[4] == "-":
        return a[:7] == b[:7]  # 2017-01-01 and 2017-01 are the same month
    return a == b


def _column_matches(agent_col: list[Any], ref_col: list[Any], ordered: bool) -> bool:
    if len(agent_col) != len(ref_col):
        return False
    for scale in (1.0, 100.0):
        if ordered:
            if all(_same(a, b, scale) for a, b in zip(agent_col, ref_col, strict=True)):
                return True
            continue
        remaining = list(agent_col)
        ok = True
        for b in ref_col:
            hit = next((i for i, a in enumerate(remaining) if _same(a, b, scale)), None)
            if hit is None:
                ok = False
                break
            remaining.pop(hit)
        if ok:
            return True
    return False


def matches(
    agent_columns: list[str],
    agent_rows: list[list[Any]] | list[tuple],
    ref_columns: list[str],
    ref_rows: list[list[Any]] | list[tuple],
    ordered: bool = False,
    match: list[str] | None = None,
) -> bool:
    if len(agent_rows) != len(ref_rows):
        return False
    agent = [[_norm(r[i]) for r in agent_rows] for i in range(len(agent_columns))]
    wanted = [i for i, c in enumerate(ref_columns) if match is None or c in match]
    for i in wanted:
        ref = [_norm(r[i]) for r in ref_rows]
        if not any(_column_matches(col, ref, ordered) for col in agent):
            return False
    return True
