"""Write the README's latest-evaluation table from the eval run's own results.

    python scripts/readme_eval.py RUN_ID --commit SHA

Reads eval/results.json and replaces the block between <!-- LATEST:START --> and
<!-- LATEST:END --> in README.md. Nothing outside the markers changes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START, END = "<!-- LATEST:START -->", "<!-- LATEST:END -->"
REPO = "https://github.com/DiegoTDDD/olist-ai-analyst"


def share(rows: list[dict], key: str) -> str:
    hits = sum(bool(r.get(key)) for r in rows)
    return f"{hits / len(rows):.0%} ({hits} of {len(rows)})"


def render(results: dict, run_id: str, commit: str) -> str:
    s, rows = results["summary"], results["questions"]
    first = sum(bool(r.get("sql_ok_first_try")) for r in rows)
    lines = [
        f"**Latest evaluation:** run [{run_id}]({REPO}/actions/runs/{run_id}) on {s['run_at']} "
        f"(commit [{commit[:7]}]({REPO}/commit/{commit})), {s['model']} on a CPU runner, "
        f"{len(rows)} questions. The weekly eval run writes this table "
        "([`scripts/readme_eval.py`](scripts/readme_eval.py)).",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Execution accuracy (result matches the reference SQL) | {share(rows, 'correct')} |",
        f"| Memos whose numbers are all in the query result | {share(rows, 'grounded')} |",
        "| Valid SQL on the first try / after retries with the error | "
        f"{first / len(rows):.0%} / {s['sql_ok_after_retries']:.0%} |",
        f"| Median time per question | {s['median_seconds']:.0f} s |",
    ]
    flagged = [r for r in rows if r.get("grounded") is False]
    if flagged:
        memos = ", ".join(
            f"[{r['id']}](eval/memos/{r['id']}.md) ({', '.join(r.get('unsupported_numbers') or [])})" for r in flagged
        )
        lines += [
            "",
            f"Memos marked **Unverified** because a number is not in their query result: {memos}.",
        ]
    return "\n".join(lines)


def replace_block(readme: str, block: str) -> str:
    if readme.count(START) != 1 or readme.count(END) != 1:
        raise SystemExit(f"README.md must contain {START} and {END} exactly once")
    head, rest = readme.split(START)
    _, tail = rest.split(END)
    return f"{head}{START}\n{block}\n{END}{tail}"


def main(argv: list[str] | None = None, root: Path = ROOT) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id")
    parser.add_argument("--commit", required=True, help="the commit the eval ran on")
    args = parser.parse_args(argv)
    results = json.loads((root / "eval" / "results.json").read_text(encoding="utf-8"))
    readme = root / "README.md"
    block = render(results, args.run_id, args.commit)
    readme.write_text(replace_block(readme.read_text(encoding="utf-8"), block), encoding="utf-8")
    print(f"README latest-evaluation table: run {args.run_id}")


if __name__ == "__main__":
    main()
