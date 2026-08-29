import math
from datetime import date

import pytest

from investigraph.template.trailing import (
    DIVIDEND_YIELD_TTM,
    MARKET_CAP,
    PE_RATIO_TTM,
    ROE_TTM,
    TrailingInput,
    TrailingMetric,
    derive_ttm_fundamentals,
    resolve_trailing,
    ttm_series,
)
from investigraph.template.models import (
    CompanyFundamentals,
    Currency,
    Market,
    MetricSeries,
    Money,
    Period,
    Point,
    Unit,
)


def _fundamentals(
    series: dict[str, MetricSeries], period: Period = Period.ANNUAL
) -> CompanyFundamentals:
    return CompanyFundamentals(
        ticker="TEST",
        market=Market.US,
        currency=Currency.USD,
        period=period,
        range="5y",
        series=series,
    )


def _money_series(
    metric_id: str,
    values_by_date: list[tuple[date, float]],
    scale: Unit = Unit.ONES,
    currency: Currency = Currency.USD,
) -> MetricSeries:
    return MetricSeries(
        metric_id=metric_id,
        points=[
            Point(date=d, value=Money(value=v, currency=currency, scale=scale))
            for d, v in values_by_date
        ],
        available=True,
    )


def _float_series(
    metric_id: str, values_by_date: list[tuple[date, float]]
) -> MetricSeries:
    return MetricSeries(
        metric_id=metric_id,
        points=[Point(date=d, value=v) for d, v in values_by_date],
        available=True,
    )


# Consecutive fiscal quarter-end dates, ~91 days apart.
_Q = [
    date(2022, 3, 31),
    date(2022, 6, 30),
    date(2022, 9, 30),
    date(2022, 12, 31),
    date(2023, 3, 31),
]


# --- ttm_series -----------------------------------------------------------


def test_ttm_series_is_identity_under_annual():
    series = _money_series("eps", [(date(2020, 1, 1), 1), (date(2021, 1, 1), 2)])

    result = ttm_series(series, Period.ANNUAL)

    assert result is series


def test_ttm_series_sums_rolling_four_quarters():
    series = _money_series("eps", [(d, 1.0) for d in _Q])

    result = ttm_series(series, Period.QUARTERLY)

    assert [p.date for p in result.points] == [_Q[3], _Q[4]]
    assert result.points[0].value.value == pytest.approx(4.0)
    assert result.points[1].value.value == pytest.approx(4.0)
    assert result.available is True


def test_ttm_series_preserves_currency_and_scale():
    series = _money_series(
        "eps", [(d, 1.0) for d in _Q], scale=Unit.MILLIONS, currency=Currency.ILS
    )

    result = ttm_series(series, Period.QUARTERLY)

    assert result.points[0].value.currency == Currency.ILS
    assert result.points[0].value.scale == Unit.MILLIONS


def test_ttm_series_unavailable_with_fewer_than_four_quarters():
    series = _money_series("eps", [(d, 1.0) for d in _Q[:3]])

    result = ttm_series(series, Period.QUARTERLY)

    assert result.available is False
    assert result.points == []


def test_ttm_series_skips_a_window_missing_a_quarter():
    # A quarter is missing between index 1 and 2 (Q3 dropped): the window
    # ending at index 3 spans far more than ~3 quarter-gaps and must be
    # skipped, while a later, healthy window still emits.
    dates = [
        date(2022, 3, 31),
        date(2022, 6, 30),
        date(2023, 3, 31),  # gap: a missing Q3/Q4
        date(2023, 6, 30),
        date(2023, 9, 30),
        date(2023, 12, 31),
    ]
    series = _money_series("eps", [(d, 1.0) for d in dates])

    result = ttm_series(series, Period.QUARTERLY)

    assert dates[3] not in [p.date for p in result.points]
    assert dates[5] in [p.date for p in result.points]


def test_ttm_series_mark_gaps_emits_nan_instead_of_skipping():
    # With mark_gaps=True (the chart-rendering path via derive_ttm_fundamentals),
    # a window missing a quarter must surface as a NaN point at that date, not
    # vanish -- an omitted point would let a line-chart renderer draw a straight
    # segment connecting the surrounding valid points *through* the gap,
    # fabricating a value nothing actually computed.
    dates = [
        date(2022, 3, 31),
        date(2022, 6, 30),
        date(2023, 3, 31),  # gap: a missing Q3/Q4
        date(2023, 6, 30),
        date(2023, 9, 30),
        date(2023, 12, 31),
    ]
    series = _money_series("eps", [(d, 1.0) for d in dates])

    result = ttm_series(series, Period.QUARTERLY, mark_gaps=True)

    result_dates = [p.date for p in result.points]
    assert dates[3] in result_dates
    gap_value = result.points[result_dates.index(dates[3])].value
    assert isinstance(gap_value, Money)
    assert math.isnan(gap_value.value)
    assert gap_value.currency == Currency.USD
    assert gap_value.scale == Unit.ONES
    assert dates[5] in result_dates
    assert result.available is True


def test_ttm_series_unavailable_when_input_unavailable():
    series = MetricSeries(metric_id="eps", points=[], available=False)

    result = ttm_series(series, Period.QUARTERLY)

    assert result.available is False


# --- resolve_trailing: as-of join mechanics --------------------------------


def test_resolve_trailing_as_of_picks_most_recent_known_value():
    fundamentals = _fundamentals(
        {
            "price": _money_series(
                "price",
                [
                    (date(2021, 1, 1), 10),
                    (date(2021, 6, 1), 20),
                    (date(2021, 12, 1), 30),
                ],
            ),
            "shares_outstanding": _float_series(
                "shares_outstanding", [(date(2021, 1, 1), 100)]
            ),
        }
    )

    series = resolve_trailing(fundamentals, MARKET_CAP)

    dates = [p.date for p in series.points]
    assert dates == [date(2021, 1, 1), date(2021, 6, 1), date(2021, 12, 1)]
    assert [p.value.value for p in series.points] == pytest.approx([1000, 2000, 3000])


def test_resolve_trailing_no_lookahead_skips_dates_before_first_input():
    fundamentals = _fundamentals(
        {
            "price": _money_series(
                "price", [(date(2019, 1, 1), 10), (date(2021, 1, 1), 20)]
            ),
            "shares_outstanding": _float_series(
                "shares_outstanding", [(date(2021, 1, 1), 100)]
            ),
        }
    )

    series = resolve_trailing(fundamentals, MARKET_CAP)

    assert [p.date for p in series.points] == [date(2021, 1, 1)]


def test_resolve_trailing_step_boundary_uses_old_value_the_day_before():
    fundamentals = _fundamentals(
        {
            "price": _money_series(
                "price",
                [
                    (date(2021, 12, 31), 10),
                    (date(2022, 1, 1), 10),
                ],
            ),
            "shares_outstanding": _float_series(
                "shares_outstanding",
                [(date(2021, 1, 1), 100), (date(2022, 1, 1), 200)],
            ),
        }
    )

    series = resolve_trailing(fundamentals, MARKET_CAP)

    values = {p.date: p.value.value for p in series.points}
    assert values[date(2021, 12, 31)] == pytest.approx(1000)  # old share count
    assert values[date(2022, 1, 1)] == pytest.approx(2000)  # new share count, same day


def test_resolve_trailing_unavailable_when_driver_missing():
    fundamentals = _fundamentals(
        {
            "shares_outstanding": _float_series(
                "shares_outstanding", [(date(2021, 1, 1), 100)]
            )
        }
    )

    series = resolve_trailing(fundamentals, MARKET_CAP)

    assert series.available is False


def test_resolve_trailing_unavailable_when_input_missing():
    fundamentals = _fundamentals(
        {"price": _money_series("price", [(date(2021, 1, 1), 10)])}
    )

    series = resolve_trailing(fundamentals, MARKET_CAP)

    assert series.available is False


def test_resolve_trailing_unavailable_when_input_marked_unavailable():
    fundamentals = _fundamentals(
        {
            "price": _money_series("price", [(date(2021, 1, 1), 10)]),
            "shares_outstanding": MetricSeries(
                metric_id="shares_outstanding", points=[], available=False
            ),
        }
    )

    series = resolve_trailing(fundamentals, MARKET_CAP)

    assert series.available is False


def test_resolve_trailing_unavailable_when_all_points_fail_compute():
    def _always_raises(price, shares):
        raise ValueError("boom")

    metric = TrailingMetric(
        metric_id="always_fails",
        title="Always Fails",
        driver="price",
        inputs=(TrailingInput("shares_outstanding"),),
        compute=_always_raises,
    )
    fundamentals = _fundamentals(
        {
            "price": _money_series("price", [(date(2021, 1, 1), 10)]),
            "shares_outstanding": _float_series(
                "shares_outstanding", [(date(2021, 1, 1), 100)]
            ),
        }
    )

    series = resolve_trailing(fundamentals, metric)

    assert series.available is False


def test_resolve_trailing_a_bad_point_breaks_the_line_with_nan_not_a_gap():
    # A per-point compute failure in the middle of the series (here: the
    # middle date's as-of shares count is zero) must not simply vanish —
    # omitting it would let a line-chart renderer draw a straight segment
    # connecting the surrounding valid points *through* the undefined date,
    # fabricating a value nothing actually computed. It should surface as
    # NaN instead, so the series stays available with a break at that date.
    def _divide(price, shares):
        return price.as_base_units() / shares

    metric = TrailingMetric(
        metric_id="sometimes_fails",
        title="Sometimes Fails",
        driver="price",
        inputs=(TrailingInput("shares_outstanding"),),
        compute=_divide,
    )
    fundamentals = _fundamentals(
        {
            "price": _money_series(
                "price",
                [
                    (date(2021, 1, 1), 10),
                    (date(2021, 6, 1), 20),
                    (date(2021, 12, 1), 30),
                ],
            ),
            "shares_outstanding": _float_series(
                "shares_outstanding",
                [
                    (date(2021, 1, 1), 100),
                    (date(2021, 6, 1), 0),
                    (date(2021, 12, 1), 50),
                ],
            ),
        }
    )

    series = resolve_trailing(fundamentals, metric)

    assert series.available is True
    dates = [p.date for p in series.points]
    values = [p.value for p in series.points]
    assert dates == [date(2021, 1, 1), date(2021, 6, 1), date(2021, 12, 1)]
    assert values[0] == pytest.approx(0.1)
    assert math.isnan(values[1])
    assert values[2] == pytest.approx(0.6)


def test_resolve_trailing_driver_none_uses_first_input_dates():
    fundamentals = _fundamentals(
        {
            "net_income": _money_series(
                "net_income", [(date(2020, 1, 1), 20), (date(2021, 1, 1), 30)]
            ),
            "total_equity": _money_series(
                "total_equity", [(date(2020, 1, 1), 200), (date(2021, 6, 1), 250)]
            ),
        }
    )

    series = resolve_trailing(fundamentals, ROE_TTM)

    dates = [p.date for p in series.points]
    assert dates == [date(2020, 1, 1), date(2021, 1, 1)]
    # 2021-01-01's net income is joined against equity as-of that date, which
    # is still the 2020-01-01 figure (2021-06-01 hasn't happened yet).
    assert series.points[1].value == pytest.approx(30 / 200)


# --- the four declared metrics ---------------------------------------------


def test_pe_ratio_ttm_divides_price_by_ttm_eps_annual():
    fundamentals = _fundamentals(
        {
            "price": _money_series("price", [(date(2021, 1, 1), 100)]),
            "eps": _money_series("eps", [(date(2021, 1, 1), 5)]),
        }
    )

    series = resolve_trailing(fundamentals, PE_RATIO_TTM)

    assert series.points[0].value == pytest.approx(20.0)


def test_pe_ratio_ttm_skips_non_positive_eps():
    fundamentals = _fundamentals(
        {
            "price": _money_series("price", [(date(2021, 1, 1), 100)]),
            "eps": _money_series("eps", [(date(2021, 1, 1), -2)]),
        }
    )

    series = resolve_trailing(fundamentals, PE_RATIO_TTM)

    assert series.available is False


def test_pe_ratio_ttm_quarterly_end_to_end():
    fundamentals = _fundamentals(
        {
            "price": _money_series("price", [(date(2023, 3, 31), 200)]),
            "eps": _money_series("eps", [(d, 1.0) for d in _Q]),
        },
        period=Period.QUARTERLY,
    )

    series = resolve_trailing(fundamentals, PE_RATIO_TTM)

    # TTM EPS at 2023-03-31 sums the trailing 4 quarters = 4.0.
    assert series.points[0].value == pytest.approx(50.0)


def test_market_cap_emits_money_points_in_price_currency():
    fundamentals = _fundamentals(
        {
            "price": _money_series(
                "price", [(date(2021, 1, 1), 10)], currency=Currency.ILS
            ),
            "shares_outstanding": _float_series(
                "shares_outstanding", [(date(2021, 1, 1), 50)]
            ),
        }
    )

    series = resolve_trailing(fundamentals, MARKET_CAP)

    assert isinstance(series.points[0].value, Money)
    assert series.points[0].value.currency == Currency.ILS
    assert series.points[0].value.scale == Unit.ONES
    assert series.points[0].value.value == pytest.approx(500)


def test_dividend_yield_ttm_annual():
    fundamentals = _fundamentals(
        {
            "price": _money_series("price", [(date(2021, 1, 1), 50)]),
            "dividends_paid": _money_series(
                "dividends_paid", [(date(2021, 1, 1), 100)]
            ),
            "shares_outstanding": _float_series(
                "shares_outstanding", [(date(2021, 1, 1), 50)]
            ),
        }
    )

    series = resolve_trailing(fundamentals, DIVIDEND_YIELD_TTM)

    # 100 / 50 shares = $2/share; 2 / 50 price = 0.04 (4%)
    assert series.points[0].value == pytest.approx(0.04)


def test_dividend_yield_ttm_quarterly_sums_dividends():
    fundamentals = _fundamentals(
        {
            "price": _money_series("price", [(date(2023, 3, 31), 100)]),
            "dividends_paid": _money_series("dividends_paid", [(d, 10.0) for d in _Q]),
            "shares_outstanding": _float_series(
                "shares_outstanding", [(date(2022, 1, 1), 40)]
            ),
        },
        period=Period.QUARTERLY,
    )

    series = resolve_trailing(fundamentals, DIVIDEND_YIELD_TTM)

    # TTM dividends = 40, / 40 shares = $1/share, / $100 price = 0.01 (1%)
    assert series.points[0].value == pytest.approx(0.01)


def test_dividend_yield_ttm_rejects_currency_mismatch():
    fundamentals = _fundamentals(
        {
            "price": _money_series(
                "price", [(date(2021, 1, 1), 50)], currency=Currency.ILS
            ),
            "dividends_paid": _money_series(
                "dividends_paid", [(date(2021, 1, 1), 100)], currency=Currency.USD
            ),
            "shares_outstanding": _float_series(
                "shares_outstanding", [(date(2021, 1, 1), 50)]
            ),
        }
    )

    series = resolve_trailing(fundamentals, DIVIDEND_YIELD_TTM)

    assert series.available is False


def test_roe_ttm_annual():
    fundamentals = _fundamentals(
        {
            "net_income": _money_series("net_income", [(date(2021, 1, 1), 25)]),
            "total_equity": _money_series("total_equity", [(date(2021, 1, 1), 200)]),
        }
    )

    series = resolve_trailing(fundamentals, ROE_TTM)

    assert series.points[0].value == pytest.approx(0.125)


def test_roe_ttm_quarterly_sums_net_income():
    fundamentals = _fundamentals(
        {
            "net_income": _money_series("net_income", [(d, 5.0) for d in _Q]),
            "total_equity": _money_series("total_equity", [(date(2022, 1, 1), 100)]),
        },
        period=Period.QUARTERLY,
    )

    series = resolve_trailing(fundamentals, ROE_TTM)

    # TTM net income at the 5th quarter = 20, / 100 equity = 0.2
    assert series.points[0].value == pytest.approx(0.2)


# --- derive_ttm_fundamentals ------------------------------------------------


def test_derive_ttm_fundamentals_rejects_non_quarterly_input():
    fundamentals = _fundamentals(
        {"revenue": _money_series("revenue", [(date(2021, 1, 1), 100)])},
        period=Period.ANNUAL,
    )

    with pytest.raises(ValueError, match="Period.QUARTERLY"):
        derive_ttm_fundamentals(fundamentals)


def test_derive_ttm_fundamentals_sums_flow_metrics():
    fundamentals = _fundamentals(
        {"revenue": _money_series("revenue", [(d, 10.0) for d in _Q])},
        period=Period.QUARTERLY,
    )

    result = derive_ttm_fundamentals(fundamentals)

    assert result.period == Period.TTM
    # 5 quarterly points -> 2 rolling 4-quarter windows survive ttm_series's warm-up.
    revenue_points = result.series["revenue"].points
    assert len(revenue_points) == 2
    assert revenue_points[-1].value.value == pytest.approx(40.0)


def test_derive_ttm_fundamentals_passes_through_point_in_time_metrics():
    equity = _money_series("total_equity", [(d, 200.0) for d in _Q])
    fundamentals = _fundamentals({"total_equity": equity}, period=Period.QUARTERLY)

    result = derive_ttm_fundamentals(fundamentals)

    # Unchanged, not summed -- a balance-sheet snapshot doesn't accumulate over quarters.
    assert result.series["total_equity"] is equity


def test_derive_ttm_fundamentals_passes_through_price_unchanged():
    price = _money_series("price", [(d, 150.0) for d in _Q])
    fundamentals = _fundamentals({"price": price}, period=Period.QUARTERLY)

    result = derive_ttm_fundamentals(fundamentals)

    assert result.series["price"] is price


def test_derive_ttm_fundamentals_recomputes_net_margin_from_ttm_flows():
    fundamentals = _fundamentals(
        {
            "net_income": _money_series("net_income", [(d, 5.0) for d in _Q]),
            "revenue": _money_series("revenue", [(d, 20.0) for d in _Q]),
            # A stale per-quarter figure that must NOT survive into the result --
            # net_margin is recomputed from the TTM'd flows, never passed through.
            "net_margin": _float_series("net_margin", [(d, 0.9) for d in _Q]),
        },
        period=Period.QUARTERLY,
    )

    result = derive_ttm_fundamentals(fundamentals)

    # TTM net_income = 20, TTM revenue = 80 -> 0.25, not 0.9.
    assert result.series["net_margin"].points[0].value == pytest.approx(0.25)


_Q_WITH_GAP = [
    date(2022, 3, 31),
    date(2022, 6, 30),
    date(2023, 3, 31),  # gap: a missing Q3/Q4
    date(2023, 6, 30),
    date(2023, 9, 30),
    date(2023, 12, 31),
]


def test_derive_ttm_fundamentals_marks_flow_metric_gap_as_nan():
    fundamentals = _fundamentals(
        {"revenue": _money_series("revenue", [(d, 10.0) for d in _Q_WITH_GAP])},
        period=Period.QUARTERLY,
    )

    result = derive_ttm_fundamentals(fundamentals)

    revenue_points = result.series["revenue"].points
    gap_point = next(p for p in revenue_points if p.date == _Q_WITH_GAP[3])
    # Flow metrics are Money-valued -- the gap marker must be too, not a bare
    # float, or every renderer expecting `.value` to be `Money` uniformly
    # crashes on this point.
    assert isinstance(gap_point.value, Money)
    assert math.isnan(gap_point.value.value)
    # A later, healthy window still emits a real value.
    healthy_point = next(p for p in revenue_points if p.date == _Q_WITH_GAP[5])
    assert healthy_point.value.value == pytest.approx(40.0)


def test_derive_ttm_fundamentals_net_margin_breaks_at_a_flow_metric_gap():
    fundamentals = _fundamentals(
        {
            "net_income": _money_series("net_income", [(d, 5.0) for d in _Q_WITH_GAP]),
            "revenue": _money_series("revenue", [(d, 20.0) for d in _Q_WITH_GAP]),
            "net_margin": _float_series("net_margin", [(d, 0.9) for d in _Q_WITH_GAP]),
        },
        period=Period.QUARTERLY,
    )

    result = derive_ttm_fundamentals(fundamentals)

    net_margin_points = result.series["net_margin"].points
    gap_point = next(p for p in net_margin_points if p.date == _Q_WITH_GAP[3])
    assert math.isnan(gap_point.value)
    healthy_point = next(p for p in net_margin_points if p.date == _Q_WITH_GAP[5])
    assert healthy_point.value == pytest.approx(0.25)


def test_derive_ttm_fundamentals_omits_net_margin_when_absent():
    fundamentals = _fundamentals(
        {"revenue": _money_series("revenue", [(d, 20.0) for d in _Q])},
        period=Period.QUARTERLY,
    )

    result = derive_ttm_fundamentals(fundamentals)

    assert "net_margin" not in result.series


def test_derive_ttm_fundamentals_gap_point_renders_without_crashing():
    # Regression test for the producer-renderer seam: a gapped flow-metric
    # series out of derive_ttm_fundamentals must be renderable by a real
    # chart, not just internally NaN-consistent. `render_money_bar` reads
    # `p.value.value`, which raises AttributeError if the gap marker were a
    # bare float instead of a Money tagged like every other point.
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from investigraph.charts.base import render_money_bar

    fundamentals = _fundamentals(
        {"revenue": _money_series("revenue", [(d, 10.0) for d in _Q_WITH_GAP])},
        period=Period.QUARTERLY,
    )

    result = derive_ttm_fundamentals(fundamentals)

    fig, ax = plt.subplots()
    render_money_bar(ax, result, "revenue")
    plt.close(fig)


def test_derive_ttm_fundamentals_approximates_gross_margin_and_notes_it():
    gross_margin = _float_series("gross_margin", [(_Q[-1], 0.42)])
    fundamentals = _fundamentals(
        {"gross_margin": gross_margin}, period=Period.QUARTERLY
    )

    result = derive_ttm_fundamentals(fundamentals)

    # Passed through as-is (the latest quarter's margin), not recomputed.
    assert result.series["gross_margin"] is gross_margin
    assert any("gross_margin" in limit for limit in result.source_limits)


def test_derive_ttm_fundamentals_skips_gross_margin_note_when_unavailable():
    fundamentals = _fundamentals(
        {"gross_margin": MetricSeries(metric_id="gross_margin", available=False)},
        period=Period.QUARTERLY,
    )

    result = derive_ttm_fundamentals(fundamentals)

    assert not any("gross_margin" in limit for limit in result.source_limits)
