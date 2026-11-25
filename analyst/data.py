"""Build the analysis database from the nine raw Olist CSV files.

The agent does not see the raw tables. It sees three analysis tables with plain column names,
one row per order, one per order item and one per seller, so a small model can answer most
questions without guessing join keys (see docs/adr/0002). The schema text the model reads is
generated from SCHEMA, so the prompt and the database cannot drift apart.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
DATABASE = ROOT / "data" / "olist.duckdb"

# Table -> (description, [(column, type, description)])
SCHEMA: dict[str, tuple[str, list[tuple[str, str, str]]]] = {
    "orders": (
        "One row per order placed on the Olist marketplace (Brazil, Sep 2016 to Oct 2018).",
        [
            ("order_id", "VARCHAR", "order key"),
            ("customer_unique_id", "VARCHAR", "the person who bought; the same person can have many orders"),
            ("customer_state", "VARCHAR", "two-letter Brazilian state of the customer, e.g. 'SP'"),
            ("customer_city", "VARCHAR", "customer city, lower case"),
            ("status", "VARCHAR", "delivered, shipped, canceled, unavailable, invoiced, processing, created, approved"),
            ("purchased_at", "TIMESTAMP", "when the order was placed"),
            ("purchase_month", "DATE", "first day of the month the order was placed"),
            ("delivered_at", "TIMESTAMP", "when the customer received it; NULL if not delivered"),
            ("estimated_delivery_date", "DATE", "delivery date promised at purchase"),
            ("delivery_days", "INTEGER", "days from purchase to delivery; NULL if not delivered"),
            ("days_late", "INTEGER", "delivery date minus promised date; negative means early; NULL if not delivered"),
            ("is_late", "BOOLEAN", "delivered after the promised date; NULL if not delivered"),
            ("items", "INTEGER", "number of items in the order"),
            ("items_value", "DOUBLE", "sum of item prices in BRL, without freight"),
            ("freight_value", "DOUBLE", "sum of freight charged in BRL"),
            ("payment_value", "DOUBLE", "total paid in BRL"),
            ("payment_type", "VARCHAR", "main payment method: credit_card, boleto, voucher, debit_card"),
            ("installments", "INTEGER", "number of credit card installments (1 if paid at once)"),
            ("review_score", "INTEGER", "customer review from 1 to 5; NULL if no review"),
        ],
    ),
    "order_items": (
        "One row per item sold. Join to orders on order_id.",
        [
            ("order_id", "VARCHAR", "order key"),
            ("item_seq", "INTEGER", "position of the item in the order, from 1"),
            ("product_id", "VARCHAR", "product key"),
            ("category", "VARCHAR", "product category in English, e.g. 'health_beauty'; 'unknown' if missing"),
            ("seller_id", "VARCHAR", "seller key"),
            ("seller_state", "VARCHAR", "two-letter state of the seller"),
            ("price", "DOUBLE", "item price in BRL"),
            ("freight_value", "DOUBLE", "freight charged for this item in BRL"),
            ("purchase_month", "DATE", "first day of the month the order was placed"),
        ],
    ),
    "sellers": (
        "One row per seller.",
        [
            ("seller_id", "VARCHAR", "seller key"),
            ("seller_city", "VARCHAR", "seller city, lower case"),
            ("seller_state", "VARCHAR", "two-letter state of the seller"),
        ],
    ),
}

# Facts about coverage that every memo should respect.
COVERAGE = (
    "Orders run from 2016-09-04 to 2018-10-17. 2016 has only a few hundred orders and the "
    "months after August 2018 are incomplete: monthly trends should use 2017-01 to 2018-08. "
    "Totals, shares and averages use all orders unless the question names a period."
)
FULL_MONTHS = ("2017-01-01", "2018-08-01")

_RAW = {
    "raw_orders": "olist_orders_dataset.csv",
    "raw_items": "olist_order_items_dataset.csv",
    "raw_payments": "olist_order_payments_dataset.csv",
    "raw_reviews": "olist_order_reviews_dataset.csv",
    "raw_customers": "olist_customers_dataset.csv",
    "raw_sellers": "olist_sellers_dataset.csv",
    "raw_products": "olist_products_dataset.csv",
    "raw_translation": "product_category_name_translation.csv",
}

_BUILD = """
CREATE OR REPLACE TABLE sellers AS
SELECT seller_id, lower(seller_city) AS seller_city, seller_state FROM raw_sellers;

CREATE OR REPLACE TABLE order_items AS
SELECT i.order_id, i.order_item_id::INTEGER AS item_seq, i.product_id,
       coalesce(t.product_category_name_english, p.product_category_name, 'unknown') AS category,
       i.seller_id, s.seller_state, i.price::DOUBLE AS price, i.freight_value::DOUBLE AS freight_value,
       date_trunc('month', o.order_purchase_timestamp::TIMESTAMP)::DATE AS purchase_month
FROM raw_items i
JOIN raw_orders o USING (order_id)
LEFT JOIN raw_products p USING (product_id)
LEFT JOIN raw_translation t USING (product_category_name)
LEFT JOIN sellers s USING (seller_id);

CREATE OR REPLACE TABLE orders AS
WITH items AS (
    SELECT order_id, count(*)::INTEGER AS items, sum(price) AS items_value, sum(freight_value) AS freight_value
    FROM order_items GROUP BY order_id
),
pay AS (
    SELECT order_id, sum(payment_value)::DOUBLE AS payment_value,
           arg_max(payment_type, payment_value) AS payment_type,
           greatest(max(payment_installments), 1)::INTEGER AS installments
    FROM raw_payments GROUP BY order_id
),
rev AS (  -- a few orders have more than one review: keep the latest
    SELECT order_id, arg_max(review_score, review_creation_date)::INTEGER AS review_score
    FROM raw_reviews GROUP BY order_id
),
base AS (
    SELECT o.order_id, c.customer_unique_id, c.customer_state, lower(c.customer_city) AS customer_city,
           o.order_status AS status,
           o.order_purchase_timestamp::TIMESTAMP AS purchased_at,
           o.order_delivered_customer_date::TIMESTAMP AS delivered_at,
           o.order_estimated_delivery_date::DATE AS estimated_delivery_date
    FROM raw_orders o JOIN raw_customers c USING (customer_id)
)
SELECT b.order_id, b.customer_unique_id, b.customer_state, b.customer_city, b.status, b.purchased_at,
       date_trunc('month', b.purchased_at)::DATE AS purchase_month,
       CASE WHEN b.status = 'delivered' THEN b.delivered_at END AS delivered_at,
       b.estimated_delivery_date,
       CASE WHEN b.status = 'delivered' THEN date_diff('day', b.purchased_at::DATE, b.delivered_at::DATE) END
           AS delivery_days,
       CASE WHEN b.status = 'delivered'
            THEN date_diff('day', b.estimated_delivery_date, b.delivered_at::DATE) END AS days_late,
       CASE WHEN b.status = 'delivered' THEN b.delivered_at::DATE > b.estimated_delivery_date END AS is_late,
       coalesce(i.items, 0) AS items, coalesce(i.items_value, 0) AS items_value,
       coalesce(i.freight_value, 0) AS freight_value, coalesce(p.payment_value, 0) AS payment_value,
       p.payment_type, coalesce(p.installments, 1) AS installments, r.review_score
FROM base b
LEFT JOIN items i USING (order_id)
LEFT JOIN pay p USING (order_id)
LEFT JOIN rev r USING (order_id);
"""


def build(raw_dir: Path = RAW_DIR, database: Path = DATABASE) -> dict[str, int]:
    """Create the three analysis tables; returns their row counts."""
    database.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(database))
    try:
        for table, filename in _RAW.items():
            path = (raw_dir / filename).as_posix()
            # quote='"' explicitly: auto-detection samples the top of the file, where nothing is
            # quoted, and then fails on later rows that are (a city name with a comma).
            con.execute(f"CREATE OR REPLACE TEMP TABLE {table} AS SELECT * FROM read_csv_auto('{path}', quote='\"')")
        con.execute(_BUILD)
        counts = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in SCHEMA}
    finally:
        con.close()
    return counts


def schema_text() -> str:
    """The schema as the model reads it."""
    parts = []
    for table, (desc, cols) in SCHEMA.items():
        lines = [f"TABLE {table} -- {desc}"]
        lines += [f"  {name} {kind} -- {text}" for name, kind, text in cols]
        parts.append("\n".join(lines))
    return "\n\n".join(parts) + f"\n\nCOVERAGE: {COVERAGE}"


def connect(database: Path = DATABASE) -> duckdb.DuckDBPyConnection:
    """Read-only, with no file or network access and the settings locked: whatever SQL the model
    writes, it cannot change the data or read anything outside it."""
    return duckdb.connect(
        str(database), read_only=True, config={"enable_external_access": False, "lock_configuration": True}
    )
