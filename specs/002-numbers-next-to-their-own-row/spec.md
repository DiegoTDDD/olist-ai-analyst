# Spec 002: numbers next to their own row

## Problem
The number check proves a number is somewhere in the result; "SP has 4.18" passes if any row
holds 4.18.

## Requirements
- R1. A number the memo ties to a row label (text cells and months) by explicit wording
  ("SP with 4.18", "4.18 in SP", "SP (4.18)", "respectively" lists) must be a value of a row with
  that label; otherwise it is reported as "number (label)".
- R2. Such a memo is not grounded: one rewrite with the wrong pairs, then **Unverified**.
- R3. The eval reports memos with a misattributed number; the README table says the grounded
  share includes the row check from run 4 on.
- R4. Gaps, ratios, counts and loose wording are not judged (no false alarms on run 3's memos).
