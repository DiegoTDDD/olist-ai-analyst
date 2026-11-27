"""The README's latest-evaluation table is rendered from eval/results.json; nothing else changes."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import readme_eval


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    rows = [{"id": f"q{i:02d}", "correct": i <= 3, "grounded": True, "sql_ok_first_try": True}
            for i in range(1, 5)]  # fmt: skip
    rows[3] |= {"grounded": False, "unsupported_numbers": ["31.2%"], "sql_ok_first_try": False}
    summary = {"model": "qwen2.5-coder:7b", "sql_ok_after_retries": 1.0, "median_seconds": 31.0,
               "run_at": "2026-11-25"}  # fmt: skip
    (tmp_path / "eval").mkdir()
    (tmp_path / "eval" / "results.json").write_text(
        json.dumps({"summary": summary, "questions": rows}), encoding="utf-8"
    )
    (tmp_path / "README.md").write_text(
        "# Title\n\n<!-- LATEST:START -->\nold\n<!-- LATEST:END -->\n\n## Why\n", encoding="utf-8"
    )
    return tmp_path


def test_renders_the_run_and_keeps_the_rest(repo):
    readme_eval.main(["45643221006", "--commit", "da47a63959fd"], root=repo)
    text = (repo / "README.md").read_text(encoding="utf-8")
    assert text.endswith("<!-- LATEST:END -->\n\n## Why\n") and "\nold\n" not in text
    assert "run [45643221006]" in text and "(commit [da47a63]" in text
    assert "| Execution accuracy (result matches the reference SQL) | 75% (3 of 4) |" in text
    assert "| Memos whose numbers are all in the query result | 75% (3 of 4) |" in text
    assert "| 75% / 100% |" in text and "| 31 s |" in text
    assert "[q04](eval/memos/q04.md) (31.2%)" in text


def test_missing_markers_fail(repo):
    (repo / "README.md").write_text("# Title\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        readme_eval.main(["1", "--commit", "abc"], root=repo)
