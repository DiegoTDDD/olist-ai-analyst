# 0005. A number the memo ties to a row must be that row's value

**Status:** Accepted

## Context
The number check (ADR 0001) proves every number in a memo exists somewhere in the query
result. It cannot tell "SP has 4.18" from "RJ has 4.18": both pass if any row holds 4.18. A
memo that swaps two states' scores, or two months' rates, would be marked verified.

## Decision
`analyst/checks.misattributed` pairs a number with a row label only where the sentence states
the pair unambiguously: "SP with 4.18", "SP: 4.18", "SP (4.18)", "4.18 in SP",
"6.19% in August 2018", and lists closed by "respectively", paired in order. Labels are the
result's text cells (states, categories) and its months ("August 2018", "Aug 2018", "2018-08").
A paired number that is a value of another row and of no row with that label is reported, as
"4.18 (RJ)". Numbers that are no row's value (gaps, ratios, counts) are left to the number
check, and looser wording is not judged.

A memo with such a number is not grounded: the model gets one rewrite with the pairs it got
wrong, and the memo is marked **Unverified** if they remain.

## Consequences
- The 25 memos of run 3 have no misattributed number, so the check adds no false alarm there;
  the unit tests build the swaps it must catch (two states, a respectively-list, two months).
- A sentence like "SP and RJ have 4.25 and 4.18" without "respectively" is not judged.
