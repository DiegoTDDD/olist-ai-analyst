# Olist AI analyst

[![tests](https://github.com/DiegoTDDD/olist-ai-analyst/actions/workflows/tests.yml/badge.svg)](https://github.com/DiegoTDDD/olist-ai-analyst/actions/workflows/tests.yml)
[![eval](https://github.com/DiegoTDDD/olist-ai-analyst/actions/workflows/eval.yml/badge.svg)](https://github.com/DiegoTDDD/olist-ai-analyst/actions/workflows/eval.yml)

A data analyst built on a local model. It takes a business question about the real Olist
marketplace data (99,441 orders, Brazil, 2016 to 2018) and returns a decision memo: the
decision the question serves, the answer, a recommendation, the SQL and rows it is based on,
the trend, and the checks it passed. Code checks every step the model takes, and an
evaluation with known answers runs on a free CI runner.

**Latest evaluation (qwen2.5-coder 7B on a CPU runner, 25 questions, 2026-11-25):**

| Metric | Value |
|---|---|
| Execution accuracy (result matches the reference SQL) | 68% (17 of 25) |
| Memos whose numbers are all in the query result | 92% |
| Valid SQL on the first try / after retries with the error | 88% / 100% |
| Median time per question | 31 s |

The two memos that failed the number check had written a rate ten times too large; both are
marked **Unverified** instead of being shown as fine.

Full results per question: [eval/results.md](eval/results.md). Every memo: [eval/memos/](eval/memos/).

## Why

An analyst's answer is worth as much as the decision it supports and the trust it earns. A
language model writing SQL fails in ways that look right: a query that runs but filters the
wrong rows, or a memo that quotes a number the query never produced. This project measures
those failures and stops the ones code can catch, instead of asking another model to judge.

## How it works

The pipeline follows the five steps of the method in the *Data-Driven Decisions* books.

| Step | What happens | Who does it |
|---|---|---|
| 1. Name the decision | The model states the decision the question serves and the metric, and writes SQL | model, JSON with a fixed schema |
| 2. Trust the data | DuckDB's parser checks the SQL: one SELECT, only the three analysis tables, no table functions. It runs on a read-only connection with file and network access off and settings locked. Empty results, all-NULL columns and truncation are flagged. Errors go back to the model, up to 3 tries | code |
| 3. Show the work | The memo carries the SQL and the rows | code |
| 4. Read the trend | A monthly series is read from a fitted line over full months only; partial months are left out and counted | code |
| 5. Make it last | Every number in the memo must exist in the result (or be a percentage, gap or ratio of values in it). The model gets one rewrite, then the memo is marked **Unverified**. The eval reruns every week | code |

The model reads three analysis tables built from the nine raw files (one row per order, one
per item, one per seller), with a description per column generated from the same definition
that builds them. See [docs/adr/0002](docs/adr/0002-three-analysis-tables.md).

## Example

From [eval/memos/q20.md](eval/memos/q20.md), "How did the monthly late delivery rate evolve
between January 2017 and August 2018?":

> **Answer:** The late delivery rate increased from 2.93% in January 2017 to 6.19% in August
> 2018, a 111.3% increase over 20 months.
>
> **Trend (computed by code):** late_delivery_rate went from 0.0293 in 2017-01 to 0.0619 in
> 2018-08 (+111.3%) over 20 full months; the trend is rising, +107.9% along a fitted line.
>
> **Checks:** SQL passed the read-only checks and ran (20 rows, 1 attempt). All numbers in this
> memo were found in the query result.

The memo also carries the SQL and the 20 rows. The rows show what a first-to-last comparison
hides: the rate spiked to 12.4% in November 2017 and 19.0% in March 2018.

## What the evaluation found

Each question has a reference SQL written by hand. An answer is correct when the agent's
result holds the same values as the reference (column names and extra columns do not matter;
counts must match exactly). See [docs/adr/0003](docs/adr/0003-execution-accuracy.md).

| Run | Change | Execution accuracy | Memos with every number in the result | Valid SQL first try |
|---|---|---|---|---|
| 1 | first run | 76%* | 79% | 92% |
| 2 | prompt and checks fixed after run 1, stricter scoring | 52%† | 92% | 88% |
| 3 | scoring bug fixed, two ambiguous questions reworded | 68% | 92% | 88% |

\* Scored with a 1% tolerance, which let a count cut short by an unrequested date filter pass.
† The stricter scoring compared decimals by their binary expansion, so an unrounded sum never
matched its rounded reference; three correct answers were scored wrong.

What each run taught:

- **Run 1.** The prompt said monthly trends should use 2017-01 to 2018-08, and the model
  applied that cut to totals and shares too (5 of 25 questions). One query used `do` as an
  alias and failed three times. The number check caught two rates written ten times too
  large ("67.9%" for 0.0679, "31.2%" for 0.0312) and an invented total for the top sellers.
  It also flagged the digits inside a seller ID as a number, which was a bug in the check.
- **Run 2.** The scoring bug above. Two questions allowed two reasonable readings ("items
  plus freight" vs. the amount paid; 1-star share of all delivered orders vs. of reviewed
  ones) and were reworded so they have one. The schema now says 8 delivered orders have no
  delivery date.
- **Run 3.** The eight misses left are the model's: a GROUP BY that keeps a NULL group next
  to late and on-time (q03), share of money instead of share of orders (q07), the date cut
  applied once more without being asked (q09), every item instead of each order's first item
  (q22, q25), order totals joined to items and counted once per item (q21), a CTE that filters
  before computing the rate (q05), and rounding to 2 decimals that ties two categories and
  swaps their order (q15). The number check caught "31.2%" for 0.0312 and "6.3%" for 0.0063.
  These are left as they are: tuning the prompt question by question would fit the eval, not
  the task.

## Limits

- The number check proves a number exists in the result, not that the sentence attaches it to
  the right row: "SP has 4.18" passes if any row holds 4.18. Execution accuracy is what catches
  a wrong answer.
- Execution accuracy scores the SQL, not the recommendation.
- 25 questions is a small set, and the questions were written by the same person who wrote the
  pipeline. Three were reworded after a run, as listed above.
- A CPU runner takes about half a minute per question: fine for a weekly eval and a CLI, not
  for an interactive product.
- The data covers 2016 to 2018 and leaves out geolocation, product dimensions and review text.

## Run it

```bash
pip install -r requirements.txt
scripts/download_data.sh          # the nine Olist CSV files, checked against SHA-256 hashes
python scripts/build_db.py        # data/olist.duckdb with the three analysis tables
ollama pull qwen2.5-coder:7b
python -m analyst "Which states have the highest late delivery rate?"
python scripts/run_eval.py --model qwen2.5-coder:7b
```

Tests (`pytest`) build the tables from a small fixture and drive the whole pipeline with a
scripted model, so they need neither the data nor a model.

## Decisions

- [0001 Code checks the model, not another model](docs/adr/0001-code-checks-the-model.md)
- [0002 Three analysis tables instead of the nine raw files](docs/adr/0002-three-analysis-tables.md)
- [0003 Score answers by running reference SQL](docs/adr/0003-execution-accuracy.md)
- [0004 A local model served by Ollama](docs/adr/0004-local-model.md)

## Data

[Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce),
CC BY-NC-SA 4.0. The same data feeds [olist-analytics](https://github.com/DiegoTDDD/olist-analytics),
the dbt project in this portfolio.
