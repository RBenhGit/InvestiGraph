from datetime import date, timedelta

import pytest

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
from investigraph.valuation.historical_pe import compute_historical_pe_averages


def _money(value: float) -> Money:
    return Money(value=value, currency=Currency.USD, scale=Unit.ONES)


def _fiscal_year_ends(count: int) -> list[date]:
    """`count` fiscal year-end dates, most-recent-first: 2025-12-31, 2024-12-31, ..."""
    return [date(2025 - i, 12, 31) for i in range(count)]


def _fundamentals(
    eps_points: list[Point], price_points: list[Point]
) -> CompanyFundamentals:
    return CompanyFundamentals(
        ticker="AAPL",
        market=Market.US,
        currency=Currency.USD,
        period=Period.ANNUAL,
        range="5y",
        series={
            "eps": MetricSeries(metric_id="eps", points=eps_points, available=True),
            "price": MetricSeries(
                metric_id="price", points=price_points, available=True
            ),
        },
    )


def _make_annual_eps(diluted_eps_values: list[float]) -> list[Point]:
    dates = _fiscal_year_ends(len(diluted_eps_values))
    return [
        Point(date=d, value=_money(eps)) for d, eps in zip(dates, diluted_eps_values)
    ]


def _make_closes(dates: list[date], close: float) -> list[Point]:
    return [Point(date=d, value=_money(close)) for d in dates]


def test_computes_avg1y_avg3y_avg5y_from_6_years_of_constant_eps_and_price():
    # Constant diluted EPS of 2/year, constant close of 20 => every annual P/E point is
    # 20/2 = 10, so every window's median is exactly 10.
    eps_points = _make_annual_eps([2] * 6)
    price_points = _make_closes([p.date for p in eps_points], 20)

    result = compute_historical_pe_averages(_fundamentals(eps_points, price_points))

    assert result.avg_1y == pytest.approx(10, abs=1e-10)
    assert result.avg_3y == pytest.approx(10, abs=1e-10)
    assert result.avg_5y == pytest.approx(10, abs=1e-10)


def test_takes_the_median_not_mean_so_one_outlier_year_does_not_dominate():
    # EPS=[1,2,2,2,2], close=[40,20,20,20,20] (most-recent-first) => P/E=[40,10,10,10,10].
    # Mean would be 16; median is 10.
    eps_points = _make_annual_eps([1, 2, 2, 2, 2])
    price_points = [
        Point(date=p.date, value=_money(40 if i == 0 else 20))
        for i, p in enumerate(eps_points)
    ]

    result = compute_historical_pe_averages(_fundamentals(eps_points, price_points))

    assert result.avg_5y == pytest.approx(10, abs=1e-10)


def test_excludes_a_non_positive_eps_year_from_its_window_rather_than_nulling_it():
    # 5 years of EPS: [2, -1, 2, 2, 2] => P/E points: [10, null, 10, 10, 10] (close=20).
    # avg5y window has 4 valid points (>= ceil(5/2)=3), median of [10,10,10,10] = 10.
    eps_points = _make_annual_eps([2, -1, 2, 2, 2])
    price_points = _make_closes([p.date for p in eps_points], 20)

    result = compute_historical_pe_averages(_fundamentals(eps_points, price_points))

    assert result.avg_5y == pytest.approx(10, abs=1e-10)


def test_nulls_a_window_when_too_few_valid_points_remain():
    # 3 years of EPS: [2, -1, -1] => P/E points: [10, null, null]. avg3y has 1 valid point,
    # short of ceil(3/2)=2, so avg3y is None. avg1y (window size 1) has its single point valid.
    eps_points = _make_annual_eps([2, -1, -1])
    price_points = _make_closes([p.date for p in eps_points], 20)

    result = compute_historical_pe_averages(_fundamentals(eps_points, price_points))

    assert result.avg_1y == pytest.approx(10, abs=1e-10)
    assert result.avg_3y is None


def test_avg3y_from_partial_history_but_avg5y_stays_null():
    # Only 2 years of history: avg3y's window has 2 valid points, meeting its ceil(3/2)=2
    # floor, so it still computes (median of [10,10]=10) even though the window isn't full.
    # avg5y's window has the same 2 valid points, short of its ceil(5/2)=3 floor -> None.
    eps_points = _make_annual_eps([2, 2])
    price_points = _make_closes([p.date for p in eps_points], 20)

    result = compute_historical_pe_averages(_fundamentals(eps_points, price_points))

    assert result.avg_1y == pytest.approx(10, abs=1e-10)
    assert result.avg_3y == pytest.approx(10, abs=1e-10)
    assert result.avg_5y is None


def test_matches_a_fiscal_year_end_to_the_nearest_preceding_close():
    eps_points = _make_annual_eps([2, 2])
    y0, y1 = eps_points[0].date, eps_points[1].date

    # y0 (most recent fiscal year-end) has no exact-date close: a later close (must be
    # skipped, being after year-end) and a gap, so the nearest PRECEDING close (24) must
    # be picked over the nearer-but-future one (999).
    price_points = [
        Point(date=y0 + timedelta(days=31), value=_money(999)),  # after y0 -- skipped
        Point(date=y0 - timedelta(days=30), value=_money(24)),  # nearest preceding
        Point(date=y1, value=_money(20)),
    ]

    result = compute_historical_pe_averages(_fundamentals(eps_points, price_points))

    # y0 -> 24/2 = 12
    assert result.avg_1y == pytest.approx(12, abs=1e-10)


def test_returns_all_none_for_a_non_annual_period_fetch():
    fundamentals = CompanyFundamentals(
        ticker="AAPL",
        market=Market.US,
        currency=Currency.USD,
        period=Period.QUARTERLY,
        range="5y",
        series={
            "eps": MetricSeries(
                metric_id="eps",
                points=_make_annual_eps([2] * 6),
                available=True,
            ),
            "price": MetricSeries(
                metric_id="price",
                points=_make_closes(_fiscal_year_ends(6), 20),
                available=True,
            ),
        },
    )

    result = compute_historical_pe_averages(fundamentals)

    assert result.avg_1y is None
    assert result.avg_3y is None
    assert result.avg_5y is None


def test_returns_all_none_when_price_series_is_missing():
    eps_points = _make_annual_eps([2] * 6)
    fundamentals = CompanyFundamentals(
        ticker="AAPL",
        market=Market.US,
        currency=Currency.USD,
        period=Period.ANNUAL,
        range="5y",
        series={
            "eps": MetricSeries(metric_id="eps", points=eps_points, available=True),
        },
    )

    result = compute_historical_pe_averages(fundamentals)

    assert result.avg_1y is None
