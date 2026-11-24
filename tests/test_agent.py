import json

from analyst.agent import MAX_SQL_TRIES, Analyst
from analyst.llm import ChatReply, ScriptedChat


def reply(**data):
    return ChatReply(content=json.dumps(data))


LATE_SQL = "SELECT round(avg(is_late::INTEGER), 4) AS late_rate FROM orders"
PLAN = reply(decision="Where to fix delivery", metric="late rate", sql=LATE_SQL)
GOOD_MEMO = reply(answer="One third of delivered orders were late: 0.3333.", recommendation="Fix the late route.",
                  caveats="Only 3 delivered orders.")  # fmt: skip


def test_happy_path_is_grounded_and_shows_the_work(con):
    model = ScriptedChat([PLAN, GOOD_MEMO])
    memo = Analyst(model, con).ask("What share of delivered orders is late?")
    assert memo.failed is None and memo.grounded
    assert memo.rows == [[0.3333]] and memo.columns == ["late_rate"]
    assert memo.llm_calls == 2 and len(memo.attempts) == 1
    md = memo.markdown()
    assert "```sql\nSELECT round(avg(is_late" in md and "| 0.3333 |" in md
    assert "All numbers in this memo were found" in md
    # the model only ever saw JSON schemas, the schema text and the result
    assert all(c["schema"] for c in model.calls)
    assert "TABLE orders" in model.calls[0]["messages"][0]["content"]
    assert "0.3333" in model.calls[1]["messages"][-1]["content"]


def test_rejected_sql_goes_back_to_the_model(con):
    bad = reply(decision="d", metric="m", sql="SELECT * FROM raw_orders")
    fixed = reply(sql="SELECT count(*) AS n FROM orders")
    memo_reply = reply(answer="There are 4 orders.", recommendation="r", caveats="c")
    model = ScriptedChat([bad, fixed, memo_reply])
    memo = Analyst(model, con).ask("How many orders?")
    assert memo.rows == [[4]] and len(memo.attempts) == 2
    assert "unknown tables" in memo.attempts[0]["error"]
    assert "rejected" in model.calls[1]["messages"][-1]["content"]


def test_gives_up_after_max_tries(con):
    steps = [reply(decision="d", metric="m", sql="DROP TABLE orders")]
    steps += [reply(sql="DROP TABLE orders")] * (MAX_SQL_TRIES - 1)
    memo = Analyst(ScriptedChat(steps), con).ask("Delete everything")
    assert memo.failed and "after 3 attempts" in memo.failed
    assert "No memo" in memo.markdown()


def test_invented_number_gets_one_rewrite(con):
    invented = reply(answer="Late rate is 0.3333, up 25% from last year.", recommendation="r", caveats="c")
    model = ScriptedChat([PLAN, invented, GOOD_MEMO])
    memo = Analyst(model, con).ask("Late share?")
    assert memo.grounded and memo.llm_calls == 3
    assert "25%" in model.calls[2]["messages"][-1]["content"]


def test_memo_still_invented_is_marked_unverified(con):
    invented = reply(answer="Late rate is 0.3333, up 25% from last year.", recommendation="r", caveats="c")
    memo = Analyst(ScriptedChat([PLAN, invented, invented]), con).ask("Late share?")
    assert not memo.grounded and memo.unsupported_numbers == ["25%"]
    assert "**Unverified:**" in memo.markdown()


def test_broken_json_from_the_model_is_handled(con):
    memo = Analyst(ScriptedChat([ChatReply(content="not json")] * MAX_SQL_TRIES), con).ask("?")
    assert memo.failed and "empty" in memo.failed


def test_trend_is_computed_by_code_and_passed_to_the_memo(con):
    sql = "SELECT purchase_month, count(*) AS orders FROM orders GROUP BY 1 ORDER BY 1"
    plan = reply(decision="d", metric="m", sql=sql)
    memo_reply = reply(answer="Orders by month are listed.", recommendation="r", caveats="c")
    model = ScriptedChat([plan, memo_reply])
    memo = Analyst(model, con).ask("Orders by month?")
    assert memo.trend is None  # only two full months in the fixture: not enough for a trend
    assert memo.rows[0][1] == 1
