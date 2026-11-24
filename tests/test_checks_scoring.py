import datetime as dt

from analyst.checks import grounding, numbers_in, trend
from analyst.scoring import matches
from analyst.sqlcheck import QueryResult


def result(columns, rows):
    return QueryResult(sql="", columns=columns, rows=rows)


def test_numbers_in_skips_dates_and_reads_formats():
    found = numbers_in("From 2017-01 to 2018-08-01, 1,234.5 orders and 8.12% late, -3 days.")
    assert [(w, v, d) for w, v, d in found] == [("1,234.5", 1234.5, 1), ("8.12%", 8.12, 2), ("-3", -3.0, 0)]


def test_grounding_accepts_values_percentages_and_rounding():
    r = result(["state", "late_rate"], [("CE", 0.1376), ("SP", 0.0589)])
    g = grounding("CE is late in 13.76% of deliveries, about 14%, against 0.06 in SP.", r)
    assert g.ok and g.checked == 3


def test_grounding_accepts_gaps_and_ratios_between_rows():
    r = result(["late", "avg_review"], [(False, 4.29), (True, 2.27)])
    assert grounding("Late orders score 2.02 points lower, 47% below on-time ones.", r).ok


def test_grounding_flags_invented_numbers():
    r = result(["n"], [(96478,)])
    g = grounding("96,478 orders were delivered, 12% more than last year.", r)
    assert not g.ok and g.unsupported == ["12%"]


def test_trend_reads_full_months_only():
    months = [dt.date(2016, 10, 1)] + [dt.date(2017, m, 1) for m in range(1, 7)] + [dt.date(2018, 9, 1)]
    values = [999, 10, 12, 14, 16, 18, 20, 1]
    t = trend(result(["purchase_month", "orders"], list(zip(months, values, strict=True))))
    assert t is not None
    assert (t.first_month, t.last_month, t.points, t.excluded_partial) == ("2017-01", "2017-06", 6, 2)
    assert t.direction == "rising" and round(t.change_pct) == 100
    assert "2017-01" in t.sentence()


def test_trend_flat_and_not_a_series():
    months = [dt.date(2017, m, 1) for m in range(1, 7)]
    flat = trend(result(["m", "v"], [(m, 100 + (i % 2)) for i, m in enumerate(months)]))
    assert flat is not None and flat.direction == "flat"
    assert trend(result(["state", "v"], [("SP", 1), ("RJ", 2), ("MG", 3), ("PR", 4)])) is None
    assert trend(result(["m", "v"], [(months[0], 1), (months[1], 2)])) is None


def test_matches_ignores_names_and_extra_columns():
    ref = (["late_rate"], [(0.0677,)])
    assert matches(["share_late", "orders"], [(0.0677, 96478)], *ref)
    assert matches(["pct"], [(6.77,)], *ref)  # same rate as a percentage
    assert matches(["x"], [(0.068,)], *ref)  # rounding within 1%
    assert not matches(["x"], [(0.08,)], *ref)


def test_matches_rankings_need_the_same_order():
    ref_cols, ref_rows = ["state", "rate"], [("CE", 0.1376), ("BA", 0.1216)]
    assert matches(["s", "r"], [("CE", 0.1376), ("BA", 0.1216)], ref_cols, ref_rows, ordered=True)
    assert not matches(["s", "r"], [("BA", 0.1216), ("CE", 0.1376)], ref_cols, ref_rows, ordered=True)
    assert matches(["s", "r"], [("BA", 0.1216), ("CE", 0.1376)], ref_cols, ref_rows, ordered=False)
    assert not matches(["s", "r"], [("CE", 0.1376)], ref_cols, ref_rows)


def test_matches_months_and_selected_columns():
    ref = (["m", "n"], [(dt.date(2017, 11, 1), 7544)])
    assert matches(["month", "orders"], [("2017-11", 7544)], *ref)
    ref3 = (["is_late", "avg_review"], [(False, 4.29), (True, 2.27)])
    assert matches(["label", "score"], [("on time", 4.29), ("late", 2.27)], *ref3, match=["avg_review"])
    assert not matches(["label", "score"], [("on time", 4.29), ("late", 2.27)], *ref3)
