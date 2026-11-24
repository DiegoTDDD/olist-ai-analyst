from analyst.data import SCHEMA, schema_text


def test_tables_have_exactly_the_documented_columns(con):
    for table, (_, cols) in SCHEMA.items():
        actual = [r[0] for r in con.execute(f"DESCRIBE {table}").fetchall()]
        assert actual == [c[0] for c in cols], table


def test_late_and_delivery_days(con):
    rows = dict(
        (r[0], r[1:])
        for r in con.execute(
            "SELECT order_id, is_late, days_late, delivery_days, delivered_at IS NULL FROM orders"
        ).fetchall()
    )
    assert rows["o1"] == (False, -4, 5, False)
    assert rows["o2"] == (True, 5, 18, False)
    assert rows["o3"] == (None, None, None, True)  # canceled orders have no delivery numbers
    assert rows["o4"] == (False, 0, 9, False)  # delivered on the promised day is on time


def test_order_totals_payment_and_latest_review(con):
    o1 = con.execute(
        "SELECT items, items_value, freight_value, payment_value, payment_type, installments, review_score "
        "FROM orders WHERE order_id = 'o1'"
    ).fetchone()
    assert o1 == (2, 150.0, 15.0, 165.0, "credit_card", 3, 5)
    # o2 has two reviews: the latest one counts
    assert con.execute("SELECT review_score FROM orders WHERE order_id = 'o2'").fetchone() == (1,)
    # 0 installments in the raw data means paid at once
    assert con.execute("SELECT installments FROM orders WHERE order_id = 'o4'").fetchone() == (1,)
    # o3 has no items or payment
    assert con.execute("SELECT items, payment_value FROM orders WHERE order_id = 'o3'").fetchone() == (0, 0.0)


def test_categories_are_translated_with_fallbacks(con):
    cats = dict(con.execute("SELECT product_id, category FROM order_items").fetchall())
    assert cats == {"p1": "health_beauty", "p2": "unknown", "p3": "categoria_sem_traducao"}


def test_same_person_across_orders(con):
    assert con.execute("SELECT count(DISTINCT customer_unique_id) FROM orders").fetchone() == (3,)


def test_schema_text_lists_every_column():
    text = schema_text()
    for table, (_, cols) in SCHEMA.items():
        assert f"TABLE {table}" in text
        for name, _, _ in cols:
            assert f"  {name} " in text
