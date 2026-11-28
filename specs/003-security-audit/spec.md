# Spec 003: Weekly dependency audit

## Problem
No workflow audits the pinned dependencies. Running pip-audit found duckdb 1.4.1 with a fixed
advisory (PYSEC-2025-112).

## Requirements
- R1 `security-audit.yml`: pip-audit over every requirements*.txt on dependency changes and
  every Monday; fail only when a fixed version exists.
- R2 Upgrade duckdb to 2.0.1 (pyproject range `>=2.0,<3`); tests and a full rebuild of
  data/olist.duckdb pass.

## Acceptance
- The audit passes in CI; 47 tests pass; the rebuilt database has 99,441 orders.
