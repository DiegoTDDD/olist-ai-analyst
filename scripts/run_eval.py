"""Run every question in eval/questions.json through the analyst and score it against the
reference SQL. Writes eval/results.json, eval/results.md and one memo per question in
eval/memos/.

    python scripts/run_eval.py --model qwen2.5-coder:3b
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyst.agent import Analyst
from analyst.data import connect
from analyst.llm import OllamaChat
from analyst.scoring import matches
from analyst.sqlcheck import run

ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / "eval"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=None)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    con = connect()
    model = OllamaChat(args.model)
    analyst = Analyst(model, con)
    questions = json.loads((EVAL / "questions.json").read_text())[: args.limit]
    (EVAL / "memos").mkdir(exist_ok=True)
    rows = []
    for q in questions:
        ref = run(con, q["sql"])
        start = time.perf_counter()
        memo = analyst.ask(q["question"])
        seconds = time.perf_counter() - start
        correct = memo.failed is None and matches(
            memo.columns, memo.rows, ref.columns, ref.rows, q.get("ordered", False), q.get("match")
        )
        rows.append({
            "id": q["id"], "question": q["question"], "correct": correct, "grounded": memo.grounded,
            "sql_ok_first_try": len(memo.attempts) == 1 and memo.failed is None,
            "attempts": len(memo.attempts), "failed": memo.failed, "numbers_checked": memo.numbers_checked,
            "unsupported_numbers": memo.unsupported_numbers, "llm_calls": memo.llm_calls,
            "seconds": round(seconds, 1), "sql": memo.sql, "reference_sql": ref.sql,
        })  # fmt: skip
        (EVAL / "memos" / f"{q['id']}.md").write_text(memo.markdown(), encoding="utf-8")
        status = f"correct={correct} grounded={memo.grounded} attempts={len(memo.attempts)}"
        print(f"{q['id']} {status} {seconds:.0f}s", flush=True)

    n = len(rows)
    answered = [r for r in rows if not r["failed"]]
    summary = {
        "model": model.name,
        "questions": n,
        "execution_accuracy": round(sum(r["correct"] for r in rows) / n, 4),
        "grounded_memos": round(sum(r["grounded"] for r in answered) / max(len(answered), 1), 4),
        "sql_ok_first_try": round(sum(r["sql_ok_first_try"] for r in rows) / n, 4),
        "sql_ok_after_retries": round(len(answered) / n, 4),
        "median_seconds": statistics.median(r["seconds"] for r in rows),
        "run_at": time.strftime("%Y-%m-%d"),
    }
    (EVAL / "results.json").write_text(json.dumps({"summary": summary, "questions": rows}, indent=2) + "\n")
    lines = [
        f"# Evaluation: {summary['model']}, {n} questions ({summary['run_at']})",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Execution accuracy (result matches the reference SQL) | {summary['execution_accuracy']:.0%} |",
        f"| Memos whose numbers are all in the query result | {summary['grounded_memos']:.0%} |",
        f"| Valid SQL on the first try | {summary['sql_ok_first_try']:.0%} |",
        f"| Valid SQL after retries with the error message | {summary['sql_ok_after_retries']:.0%} |",
        f"| Median seconds per question (CPU runner) | {summary['median_seconds']:.0f} |",
        "",
        "| # | Question | Correct | Grounded | SQL tries | Seconds |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(f"| [{r['id']}](memos/{r['id']}.md) | {r['question']} | {'yes' if r['correct'] else 'no'} | "
                     f"{'yes' if r['grounded'] else 'no'} | {r['attempts']} | {r['seconds']:.0f} |")  # fmt: skip
    (EVAL / "results.md").write_text("\n".join(lines) + "\n")
    hist = EVAL / "history.jsonl"
    with hist.open("a") as f:
        f.write(json.dumps(summary) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
