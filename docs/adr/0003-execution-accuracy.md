# 0003: Score answers by running reference SQL

## Context

A memo can read well and still be wrong. Judging prose with another model is noisy and hides
what was actually wrong.

## Decision

Each question in `eval/questions.json` has a reference SQL written by hand. The agent's result
counts as correct when every reference column appears among the agent's columns with the same
values: in order for rankings, as a multiset otherwise, within 1% (a rate written as a
percentage also matches). Column names and extra columns do not matter. For questions where a
label column can be written many ways (true/false or "late"/"on time"), the question lists the
columns to compare. The eval also reports the share of memos whose numbers all passed the
number check, SQL valid on the first try and after retries, and time per question.

## Consequences

The score is reproducible and each failure points at a query that can be read. It measures the
SQL, not the recommendation; the recommendation is constrained by the number check instead.
The questions are written to have one reasonable reading (for example "among states with at
least 1000 delivered orders"), so a miss is the model's, not the question's.
