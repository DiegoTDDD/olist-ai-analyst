"""Numbers tied to a row in the memo must be that row's values."""

from analyst.checks import misattributed
from analyst.sqlcheck import QueryResult


def _states() -> QueryResult:
    return QueryResult(sql="", columns=["state", "avg_score"], rows=[("SP", 4.18), ("RJ", 4.25), ("MG", 4.1)])


def test_a_number_next_to_its_own_row_passes():
    assert misattributed("SP has 4.18, RJ has 4.25 and MG 4.10.", _states()) == []
    assert misattributed("The best are RJ and SP, with 4.25 and 4.18 respectively.", _states()) == []


def test_a_number_next_to_another_row_is_reported():
    assert misattributed("SP has 4.25.", _states()) == ["4.25 (SP)"]
    assert misattributed("The best are RJ and SP, with 4.18 and 4.25 respectively.", _states()) == [
        "4.18 (RJ)", "4.25 (SP)"]  # fmt: skip


def test_months_and_derived_numbers():
    import datetime as dt

    monthly = QueryResult(sql="", columns=["month", "late_rate"],
                          rows=[(dt.date(2017, 1, 1), 0.0293), (dt.date(2018, 8, 1), 0.0619)])  # fmt: skip
    ok = "The rate rose from 2.93% in January 2017 to 6.19% in August 2018, a 111.3% increase."
    assert misattributed(ok, monthly) == []
    assert misattributed("It was 6.19% in January 2017.", monthly) == ["6.19% (January 2017)"]
    # 3.26 is no row's value (a gap): not judged here, the number check handles it
    assert misattributed("August 2018 was 3.26 points above.", monthly) == []
