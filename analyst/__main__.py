"""Ask a business question and print the decision memo.

python -m analyst "Which states have the highest late delivery rate?"
"""

from __future__ import annotations

import argparse
import sys

from analyst.agent import Analyst
from analyst.data import DATABASE, connect
from analyst.llm import OllamaChat


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("question")
    parser.add_argument("--model", default=None, help="Ollama model (default: $ANALYST_MODEL or qwen2.5-coder:3b)")
    args = parser.parse_args()
    if not DATABASE.exists():
        sys.exit("no database yet: run scripts/download_data.sh, then python scripts/build_db.py")
    memo = Analyst(OllamaChat(args.model), connect()).ask(args.question)
    sys.stdout.write(memo.markdown())


if __name__ == "__main__":
    main()
