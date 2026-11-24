"""A tiny Olist: raw CSV files written by the tests, built by the real build code."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from analyst.data import build, connect

RAW = {
    "olist_orders_dataset.csv": (
        ["order_id", "customer_id", "order_status", "order_purchase_timestamp", "order_approved_at",
         "order_delivered_carrier_date", "order_delivered_customer_date", "order_estimated_delivery_date"],
        [
            # on time, 4 days early
            ["o1", "c1", "delivered", "2017-03-01 10:00:00", "", "", "2017-03-06 12:00:00", "2017-03-10 00:00:00"],
            # 5 days late
            ["o2", "c2", "delivered", "2017-04-02 09:00:00", "", "", "2017-04-20 08:00:00", "2017-04-15 00:00:00"],
            # canceled: no delivery numbers
            ["o3", "c3", "canceled", "2018-01-05 11:00:00", "", "", "", "2018-01-25 00:00:00"],
            # same person as o1 (customer_unique_id u1), delivered on the promised day
            ["o4", "c4", "delivered", "2018-09-03 15:00:00", "", "", "2018-09-12 10:00:00", "2018-09-12 00:00:00"],
        ],
    ),
    "olist_customers_dataset.csv": (
        ["customer_id", "customer_unique_id", "customer_zip_code_prefix", "customer_city", "customer_state"],
        [["c1", "u1", "01000", "Sao Paulo", "SP"], ["c2", "u2", "20000", "Rio de Janeiro", "RJ"],
         ["c3", "u3", "30000", "Belo Horizonte", "MG"], ["c4", "u1", "01000", "Sao Paulo", "SP"]],
    ),
    "olist_order_items_dataset.csv": (
        ["order_id", "order_item_id", "product_id", "seller_id", "shipping_limit_date", "price", "freight_value"],
        [["o1", "1", "p1", "s1", "", "100.0", "10.0"], ["o1", "2", "p2", "s2", "", "50.0", "5.0"],
         ["o2", "1", "p1", "s1", "", "100.0", "20.0"], ["o4", "1", "p3", "s2", "", "30.0", "7.5"]],
    ),
    "olist_order_payments_dataset.csv": (
        ["order_id", "payment_sequential", "payment_type", "payment_installments", "payment_value"],
        [["o1", "1", "credit_card", "3", "150.0"], ["o1", "2", "voucher", "1", "15.0"],
         ["o2", "1", "boleto", "1", "120.0"], ["o4", "1", "credit_card", "0", "37.5"]],
    ),
    "olist_order_reviews_dataset.csv": (
        ["review_id", "order_id", "review_score", "review_comment_title", "review_comment_message",
         "review_creation_date", "review_answer_timestamp"],
        [["r1", "o1", "5", "", "", "2017-03-07 00:00:00", ""], ["r2", "o2", "4", "", "", "2017-04-21 00:00:00", ""],
         ["r3", "o2", "1", "", "", "2017-04-25 00:00:00", ""], ["r4", "o4", "3", "", "", "2018-09-13 00:00:00", ""]],
    ),
    "olist_sellers_dataset.csv": (
        ["seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"],
        [["s1", "01000", "Sao Paulo", "SP"], ["s2", "80000", "Curitiba", "PR"]],
    ),
    "olist_products_dataset.csv": (
        ["product_id", "product_category_name", "product_name_lenght", "product_description_lenght",
         "product_photos_qty", "product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"],
        [["p1", "beleza_saude", "", "", "", "", "", "", ""], ["p2", "", "", "", "", "", "", "", ""],
         ["p3", "categoria_sem_traducao", "", "", "", "", "", "", ""]],
    ),
    "product_category_name_translation.csv": (
        ["product_category_name", "product_category_name_english"], [["beleza_saude", "health_beauty"]],
    ),
}  # fmt: skip


@pytest.fixture(scope="session")
def database(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("olist")
    raw = root / "raw"
    raw.mkdir()
    for name, (header, rows) in RAW.items():
        with (raw / name).open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
    db = root / "olist.duckdb"
    build(raw, db)
    return db


@pytest.fixture
def con(database: Path):
    c = connect(database)
    yield c
    c.close()
