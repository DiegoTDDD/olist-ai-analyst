# Spec 001: the README's latest-evaluation table is written by the eval run

## Problem
The eval reruns every Monday and commits `eval/results.*`, but the README's "Latest
evaluation" table is typed by hand. The first rerun that moves a number would leave the
README showing an older run without saying so.

## Requirements
- R1. The eval workflow rewrites the block between `<!-- LATEST:START -->` and
  `<!-- LATEST:END -->` from `eval/results.json`: run id, date, commit, model, the four
  metrics with counts, and the memos marked Unverified with the numbers that failed.
- R2. Text outside the markers is never changed; missing markers fail loudly.
- R3. The run-by-run history (what each run taught) stays written by hand.
