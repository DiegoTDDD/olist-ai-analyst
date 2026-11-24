import pytest

from analyst.sqlcheck import MAX_ROWS, SQLRejected, check, clean, run


def test_runs_a_plain_query(con):
    r = run(con, "SELECT customer_state, count(*) AS n FROM orders GROUP BY 1 ORDER BY 1")
    assert r.columns == ["customer_state", "n"]
    assert r.rows == [("MG", 1), ("RJ", 1), ("SP", 2)]
    assert r.warnings == []


def test_accepts_ctes_and_markdown_fences(con):
    sql = "```sql\nWITH x AS (SELECT * FROM orders) SELECT count(*) AS n FROM x;\n```"
    assert run(con, sql).rows == [(4,)]
    assert clean(" SELECT 1; ") == "SELECT 1"


@pytest.mark.parametrize(
    ("sql", "message"),
    [
        ("", "empty"),
        ("SELECT 1; SELECT 2", "exactly one"),
        ("DROP TABLE orders", "only SELECT"),
        ("COPY orders TO 'out.csv'", "only SELECT"),
        ("ATTACH 'other.db'", "only SELECT"),
        ("SELECT * FROM raw_orders", "unknown tables"),
        ("SELECT * FROM duckdb_tables()", "table functions"),
        ("SELECT * FROM range(10)", "table functions"),
        ("SELECT * FROM read_csv('/etc/passwd')", "disabled"),
        ("SELECT nope FROM orders", "query failed"),
        ("SELEC count(*) FROM orders", "does not parse"),
    ],
)
def test_rejects(con, sql, message):
    with pytest.raises(SQLRejected, match=message):
        run(con, sql)


def test_keywords_inside_strings_are_fine(con):
    assert check(con, "SELECT 'drop table orders' AS s FROM orders LIMIT 1")


def test_connection_cannot_write_or_reconfigure(con):
    import duckdb

    with pytest.raises(duckdb.Error):
        con.execute("CREATE TABLE x AS SELECT 1")
    with pytest.raises(duckdb.Error):
        con.execute("SET enable_external_access = true")


def test_row_cap_and_warnings(con):
    r = run(con, f"SELECT * FROM orders o, (SELECT unnest(range({MAX_ROWS})) AS i) AS t")
    assert len(r.rows) == MAX_ROWS and r.truncated
    assert any("only the first" in w for w in r.warnings)
    empty = run(con, "SELECT order_id FROM orders WHERE 1 = 0")
    assert empty.warnings == ["the query returned no rows"]
    nulls = run(con, "SELECT delivered_at FROM orders WHERE status = 'canceled'")
    assert nulls.warnings == ["column delivered_at is empty (all NULL)"]
