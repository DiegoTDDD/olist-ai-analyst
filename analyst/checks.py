"""Deterministic checks on what the model says: every number in the memo must come from the
query result, and the trend is computed by code, never described by the model from memory."""

from __future__ import annotations

import datetime as dt
import math
import re
from dataclasses import dataclass

from analyst.data import FULL_MONTHS
from analyst.sqlcheck import QueryResult

# 1,234.5 / 12.3% / -0.07 / 2017-01 (dates are skipped, see _DATE)
_NUMBER = re.compile(r"(?<![\w.])-?\d+(?:,\d{3})*(?:\.\d+)?%?(?![\w])")  # not inside an ID like 4869f7a5
_DATE = re.compile(r"\b\d{4}-\d{2}(?:-\d{2})?\b")


def numbers_in(text: str) -> list[tuple[str, float, int]]:
    """(as written, value, decimals) for each number in the text, ignoring dates like 2017-03."""
    text = _DATE.sub(" ", text)
    out = []
    for m in _NUMBER.finditer(text):
        raw = m.group(0).rstrip("%")
        decimals = len(raw.split(".")[1]) if "." in raw else 0
        out.append((m.group(0), float(raw.replace(",", "")), decimals))
    return out


def _numeric(v: object) -> float | None:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, int | float):
        return float(v) if math.isfinite(float(v)) else None
    try:  # Decimal and numpy types
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def allowed_values(result: QueryResult, question: str = "") -> list[float]:
    """Numbers a memo may use: result values, the same as percentages or shares, simple
    differences and ratios between values in the same column, years, and numbers in the question."""
    values: list[float] = []
    for i in range(len(result.columns)):
        col = [x for x in (_numeric(r[i]) for r in result.rows) if x is not None]
        values += col
        values += [x * 100 for x in col] + [x / 100 for x in col]
        if 2 <= len(col) <= 60:  # gaps and ratios between rows: "1.3 points lower", "2.1 times"
            for a in col:
                for b in col:
                    if a != b:
                        values.append(a - b)
                        if b:
                            values += [a / b, (a / b - 1) * 100, abs(a / b - 1) * 100]
        for r in result.rows:
            if isinstance(r[i], dt.date):
                values += [r[i].year, r[i].month]
    values += [v for _, v, _ in numbers_in(question)]
    values += list(range(max(len(result.rows), 10) + 1))  # counts and ranks: "top 3", "5 states"
    return values


@dataclass
class Grounding:
    checked: int
    unsupported: list[str]

    @property
    def ok(self) -> bool:
        return not self.unsupported


def grounding(text: str, result: QueryResult, question: str = "") -> Grounding:
    allowed = allowed_values(result, question)
    found = numbers_in(text)
    bad = []
    for written, value, decimals in found:
        tol = max(0.5 * 10**-decimals, 0.005 * abs(value)) + 1e-9
        if not any(abs(value - a) <= tol for a in allowed):
            bad.append(written)
    return Grounding(checked=len(found), unsupported=bad)


_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"]  # fmt: skip


def _labels(cell: object) -> list[str]:
    """How a memo may name a row by this cell: a state or category as written, a month as
    "January 2017", "Jan 2017" or "2017-01"."""
    if isinstance(cell, dt.date):
        d = _as_date(cell)
        name = _MONTHS[d.month - 1]
        return [f"{name} {d.year}", f"{name[:3]} {d.year}", f"{d.year}-{d.month:02d}"]
    if isinstance(cell, str) and len(cell.strip()) >= 2 and _numeric(cell) is None:
        return [cell.strip(), cell.strip().replace("_", " ")]
    return []


def _row_values(row: tuple) -> list[float]:
    vals = [x for x in (_numeric(c) for c in row) if x is not None]
    return vals + [x * 100 for x in vals]


def _matches(value: float, decimals: int, candidates: list[float]) -> bool:
    tol = max(0.5 * 10**-decimals, 0.005 * abs(value)) + 1e-9
    return any(abs(value - c) <= tol for c in candidates)


_CONNECT_AFTER = re.compile(r"^\s*(?:\)\s*)?(?:(?:with|has|had|at|of|is|was|:|=|-)\s*){1,3}(?:R\$\s*)?$", re.I)
_CONNECT_BEFORE = re.compile(r"^\s*(?:in|for|on|from|by)\s+(?:the\s+)?$", re.I)


Label = tuple[int, int, str]  # start, end, label as found in the sentence


def _pairs(sentence: str, labels: list[Label], numbers: list[re.Match]) -> list[tuple[re.Match, Label]]:
    """(number, label) pairs the sentence states unambiguously.

    "SP with 4.18", "SP: 4.18", "SP (4.18)", "4.18 in SP", "2.93% in January 2017", and lists
    closed by "respectively" (paired in order). Anything looser is not judged."""
    if re.search(r"\brespectively\b", sentence, re.I):
        seen: list[tuple[int, int, str]] = []
        for lb in labels:
            if lb[2] not in {x[2] for x in seen}:
                seen.append(lb)
        return list(zip(numbers, seen, strict=True)) if len(seen) == len(numbers) else []
    out = []
    for m in numbers:
        before = [
            lb
            for lb in labels
            if lb[1] <= m.start() and _CONNECT_AFTER.match(sentence[lb[1] : m.start()].replace("(", ""))
        ]
        after = [lb for lb in labels if lb[0] >= m.end() and _CONNECT_BEFORE.match(sentence[m.end() : lb[0]])]
        if len(before) + len(after) == 1:
            out.append((m, (before or after)[0]))
    return out


def misattributed(text: str, result: QueryResult) -> list[str]:
    """Numbers the memo puts next to the wrong row.

    The number check proves a number is somewhere in the result; "SP has 4.18" passes if any
    row holds 4.18. Here a number the sentence ties to a row label (a state, a category, a
    month: "SP with 4.18", "6.19% in August 2018", lists closed by "respectively") must be a
    value of a row with that label. It is reported as "4.18 (SP)" when it is another row's value
    instead. Numbers that are no row's value (gaps, ratios, counts) and looser wording are not
    judged.
    """
    label_rows: dict[str, list[int]] = {}
    for i, row in enumerate(result.rows):
        for cell in row:
            for label in _labels(cell):
                label_rows.setdefault(label.lower(), []).append(i)
    if not label_rows:
        return []
    pattern = re.compile(
        r"(?<![\w-])(" + "|".join(re.escape(lb) for lb in sorted(label_rows, key=len, reverse=True)) + r")(?![\w-])",
        re.IGNORECASE,
    )
    all_values = [_row_values(r) for r in result.rows]
    bad = []
    for sentence in re.split(r"(?<=[.;!?])\s+", text):
        labels = [(m.start(), m.end(), m.group(1).lower()) for m in pattern.finditer(sentence)]
        if not labels:
            continue
        masked = _DATE.sub(lambda m: " " * len(m.group(0)), sentence)
        numbers = [m for m in _NUMBER.finditer(masked)
                   if not any(a <= m.start() < b for a, b, _ in labels)]  # fmt: skip
        for m, (start, end, label) in _pairs(sentence, labels, numbers):
            raw = m.group(0).rstrip("%")
            value = float(raw.replace(",", ""))
            decimals = len(raw.split(".")[1]) if "." in raw else 0
            owners = {i for i, vals in enumerate(all_values) if _matches(value, decimals, vals)}
            if owners and not owners & set(label_rows[label]):
                bad.append(f"{m.group(0)} ({sentence[start:end]})")
    return bad


@dataclass
class Trend:
    column: str
    first_month: str
    last_month: str
    first: float
    last: float
    change_pct: float | None
    fitted_change_pct: float | None
    direction: str
    points: int
    excluded_partial: int

    def sentence(self) -> str:
        change = "" if self.change_pct is None else f" ({self.change_pct:+.1f}%)"
        fitted = "" if self.fitted_change_pct is None else f", {self.fitted_change_pct:+.1f}% along a fitted line"
        return (f"{self.column} went from {fmt(self.first)} in {self.first_month} to {fmt(self.last)} in "
                f"{self.last_month}{change} over {self.points} full months; "
                f"the trend is {self.direction}{fitted}.")  # fmt: skip


def trend(result: QueryResult) -> Trend | None:
    """If the result is a monthly series, compare its first and last full months with a fitted
    line (so one odd month cannot set the direction). Partial months are left out."""
    date_idx = [i for i, _ in enumerate(result.columns)
                if result.rows and all(isinstance(r[i], dt.date) for r in result.rows)]  # fmt: skip
    if len(date_idx) != 1 or len(result.rows) < 4:
        return None
    d = date_idx[0]
    if len({r[d] for r in result.rows}) != len(result.rows):
        return None  # several rows per month (a breakdown), not one series
    lo, hi = (dt.date.fromisoformat(x) for x in FULL_MONTHS)
    rows = sorted(result.rows, key=lambda r: r[d])
    full = [r for r in rows if lo <= _as_date(r[d]) <= hi]
    if len(full) < 4:
        return None
    num_idx = [i for i in range(len(result.columns))
               if i != d and all(_numeric(r[i]) is not None for r in full)]  # fmt: skip
    if not num_idx:
        return None
    v = num_idx[-1]  # the last numeric column is usually the measure (counts come first)
    ys = [float(r[v]) for r in full]
    n = len(ys)
    xs = list(range(n))
    mx, my = sum(xs) / n, sum(ys) / n
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / sum((x - mx) ** 2 for x in xs)
    fitted_first, fitted_last = my - slope * mx, my + slope * (n - 1 - mx)
    change = None if fitted_first == 0 else (fitted_last / fitted_first - 1) * 100
    if change is None:
        direction = "flat" if slope == 0 else ("rising" if slope > 0 else "falling")
    else:
        direction = "flat" if abs(change) < 5 else ("rising" if change > 0 else "falling")
    return Trend(
        column=result.columns[v],
        first_month=str(_as_date(full[0][d]))[:7],
        last_month=str(_as_date(full[-1][d]))[:7],
        first=ys[0],
        last=ys[-1],
        change_pct=None if ys[0] == 0 else (ys[-1] / ys[0] - 1) * 100,
        fitted_change_pct=change,
        direction=direction,
        points=n,
        excluded_partial=len(rows) - n,
    )


def fmt(x: float) -> str:
    """Enough digits to be useful: 6,512 / 12.35 / 0.0337."""
    if abs(x) >= 1000 or float(x).is_integer():
        return f"{x:,.0f}" if float(x).is_integer() else f"{x:,.1f}"
    return f"{x:.2f}" if abs(x) >= 1 else f"{x:.4f}"


def _as_date(v: dt.date) -> dt.date:
    return v.date() if isinstance(v, dt.datetime) else v
