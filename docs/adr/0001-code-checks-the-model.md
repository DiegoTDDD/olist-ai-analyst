# 0001: Code checks the model, not another model

## Context

A small local model writes the SQL and the memo. It can write SQL that does not run, SQL that
runs but answers something else, and a memo that states numbers the query never produced. A
second model acting as judge would cost another call per question and would share the same
blind spots.

## Decision

Everything that can be checked by code is checked by code:

- The SQL goes through DuckDB's own parser: one statement, a SELECT, only the three analysis
  tables, no table functions. The connection is read-only, has file and network access turned
  off and its settings locked, so a query cannot write, read files or turn access back on.
- A result with no rows, an all-NULL column or more than 200 rows gets a warning in the memo.
- The trend of a monthly series is computed by code from a fitted line over full months; the
  model receives the sentence and cannot describe the trend from memory.
- Every number in the memo must match a value in the result (or a percentage, difference or
  ratio of values, a year, a count of rows, or a number from the question). The model gets one
  rewrite; after that the memo is marked **Unverified** and lists the numbers it could not find.

## Consequences

The checks are cheap and deterministic, and the tests cover them without a model. The number
check proves a number exists in the result, not that the sentence attaches it to the right
row: "SP has 4.18" passes if any row holds 4.18. The eval's execution accuracy is what catches
a wrong answer.
