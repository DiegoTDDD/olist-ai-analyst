# 0002: Three analysis tables instead of the nine raw files

## Context

The raw Olist data has nine tables with several traps: reviews duplicated per order, payments
split across rows, delivery dates that only mean something for delivered orders, category names
in Portuguese with a separate translation table. A small model writing joins over all of that
gets the grain wrong.

## Decision

`scripts/build_db.py` builds three tables the model reads: `orders` (one row per order, with
delivery, lateness, totals, main payment type and the latest review), `order_items` (one row
per item, with the English category and the seller's state) and `sellers`. The schema the
model sees is generated from the same definition that builds the tables, with a description
per column and the data's coverage dates, and a test checks that the built tables have exactly
the documented columns.

## Consequences

Most questions need one table or one join on `order_id`. Decisions about the data (latest
review wins, lateness by calendar day, "unknown" for missing categories) are made once, in
SQL that is tested on a fixture, instead of by the model on every question. Questions about
things left out (geolocation, product dimensions, review text) cannot be answered.
