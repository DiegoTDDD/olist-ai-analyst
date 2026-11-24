# 0004: A local model served by Ollama

## Context

The project has to run for free, on a laptop or a CI runner, and the data never needs to leave
the machine.

## Decision

The model runs in Ollama, asked for JSON with a fixed schema at each step (plan and SQL, a fixed
SQL, the memo) at temperature 0 with a fixed seed. The model is a parameter; the weekly eval
runs on the GitHub runner's CPU and commits its results, so a change in the model or a
dependency shows up as a change in the numbers.

## Consequences

No API key and no cost. A CPU runner takes tens of seconds per question, which is fine for a
weekly eval and a CLI, not for an interactive product. The interface to the model is one
method, so a hosted model is one class away.
