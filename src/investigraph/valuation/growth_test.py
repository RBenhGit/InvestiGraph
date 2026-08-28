import math
from datetime import date

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
from investigraph.valuation.growth import (
    calculate_cagr_percent,
    calculate_ttm_eps_growth_percent,
    historical_1y_growth_percent,
    historical_3y_growth_percent,
    resolve_growth_rate_percent,
)


def _money(value: float) -> Money:
    return Money(value=value, currency=Currency.USD, scale=Unit.ONES)


def _annual_fundamentals(eps_by_date: dict[date, float]) -> CompanyFundamentals:
    return CompanyFundamentals(
        ticker="TEST",
        market=Market.US,
        currency=Currency.USD,
        period=Period.ANNUAL,
        range="5y",
        series={
            "eps": MetricSeries(
                metric_id="eps",
                points=[Point(date=d, value=_money(v)) for d, v in eps_by_date.items()],
                available=True,
            )
        },
    )


def _quarterly_fundamentals(eps_by_date: dict[date, float]) -> CompanyFundamentals:
    return CompanyFundamentals(
        ticker="TEST",
        market=Market.US,
        currency=Currency.USD,
        period=Period.QUARTERLY,
        range="5y",
        series={
            "eps": MetricSeries(
                metric_id="eps",
                points=[Point(date=d, value=_money(v)) for d, v in eps_by_date.items()],
                available=True,
            )
        },
    )


# --- calculate_cagr_percent ------------------------------------------------


def test_cagr_basic_growth():
    assert calculate_cagr_percent(3.0, 2.0, 3) == pytest.approx(
        (math.pow(3.0 / 2.0, 1 / 3) - 1) * 100
    )


def test_cagr_none_when_either_input_is_none():
    assert calculate_cagr_percent(None, 2.0, 1) is None
    assert calculate_cagr_percent(3.0, None, 1) is None


def test_cagr_none_when_eps_past_is_zero_or_negative():
    # A company swinging from a loss (or breakeven) to a profit has no meaningful
    # CAGR in this formula.
    assert calculate_cagr_percent(3.0, 0.0, 1) is None
    assert calculate_cagr_percent(3.0, -1.0, 1) is None


def test_cagr_none_when_years_is_not_positive():
    assert calculate_cagr_percent(3.0, 2.0, 0) is None
    assert calculate_cagr_percent(3.0, 2.0, -1) is None


def test_cagr_none_not_nan_on_a_profit_to_loss_swing():
    # eps_latest negative, eps_past positive: the ratio is negative, and raising a
    # negative number to a fractional power is undefined (NaN in floating point) for
    # years > 1. Must surface as None, never NaN — a NaN would be treated as
    # "usable" by every fallback chain that checks `is not None`.
    result = calculate_cagr_percent(-1.0, 2.0, 3)
    assert result is None


def test_cagr_result_is_never_nan():
    result = calculate_cagr_percent(-1.0, 2.0, 3)
    assert result is None or not math.isnan(result)


# --- historical_1y_growth_percent / historical_3y_growth_percent -----------


def test_historical_1y_and_3y_growth_from_annual_eps_series():
    fundamentals = _annual_fundamentals(
        {
            date(2022, 12, 31): 2.0,
            date(2023, 12, 31): 2.2,
            date(2024, 12, 31): 2.5,
            date(2025, 12, 31): 3.0,
        }
    )

    assert historical_1y_growth_percent(fundamentals) == pytest.approx(
        (3.0 / 2.5 - 1) * 100
    )
    assert historical_3y_growth_percent(fundamentals) == pytest.approx(
        (math.pow(3.0 / 2.0, 1 / 3) - 1) * 100
    )


def test_historical_1y_needs_at_least_2_annual_points():
    fundamentals = _annual_fundamentals({date(2025, 12, 31): 3.0})
    assert historical_1y_growth_percent(fundamentals) is None


def test_historical_3y_needs_at_least_4_annual_points():
    fundamentals = _annual_fundamentals(
        {
            date(2023, 12, 31): 2.2,
            date(2024, 12, 31): 2.5,
            date(2025, 12, 31): 3.0,
        }
    )
    assert historical_3y_growth_percent(fundamentals) is None


def test_historical_growth_is_none_when_eps_series_is_unavailable():
    fundamentals = CompanyFundamentals(
        ticker="TEST",
        market=Market.US,
        currency=Currency.USD,
        period=Period.ANNUAL,
        range="5y",
        series={},
    )
    assert historical_1y_growth_percent(fundamentals) is None
    assert historical_3y_growth_percent(fundamentals) is None


def test_historical_growth_is_none_for_a_quarterly_period_fetch():
    # historical_1y/3y compare *annual* EPS points; a quarterly-period fetch
    # doesn't have that shape even if it happens to hold an `eps` series.
    fundamentals = _quarterly_fundamentals(
        {
            date(2025, 3, 31): 0.5,
            date(2025, 6, 30): 0.6,
        }
    )
    assert historical_1y_growth_percent(fundamentals) is None
    assert historical_3y_growth_percent(fundamentals) is None


# --- resolve_growth_rate_percent (the fallback chain) -----------------------


def test_resolve_growth_rate_prefers_analyst_estimate():
    assert resolve_growth_rate_percent(12.0, 8.0, 5.0) == 12.0


def test_resolve_growth_rate_falls_back_to_historical_3y():
    assert resolve_growth_rate_percent(None, 8.0, 5.0) == 8.0


def test_resolve_growth_rate_falls_back_to_historical_1y():
    assert resolve_growth_rate_percent(None, None, 5.0) == 5.0


def test_resolve_growth_rate_is_none_when_all_three_are_none():
    # The one thing this function must never do: fabricate a 0 here, which
    # downstream would silently produce a $0 "fair value" instead of surfacing
    # MISSING_GROWTH_RATE.
    assert resolve_growth_rate_percent(None, None, None) is None


def test_resolve_growth_rate_treats_a_real_zero_as_usable_not_missing():
    # 0.0 is a legitimate growth rate (flat EPS) and must not be skipped the way
    # None is — mirrors the original TS's `??` semantics (falls through on
    # null/undefined only, never on a real 0).
    assert resolve_growth_rate_percent(0.0, 8.0, 5.0) == 0.0
    assert resolve_growth_rate_percent(None, 0.0, 5.0) == 0.0
    assert resolve_growth_rate_percent(None, None, 0.0) == 0.0


# --- calculate_ttm_eps_growth_percent ---------------------------------------


def _eight_quarters(values: list[float]) -> dict[date, float]:
    assert len(values) == 8
    dates = [
        date(2024, 3, 31),
        date(2024, 6, 30),
        date(2024, 9, 30),
        date(2024, 12, 31),
        date(2025, 3, 31),
        date(2025, 6, 30),
        date(2025, 9, 30),
        date(2025, 12, 31),
    ]
    return dict(zip(dates, values))


def test_ttm_eps_growth_from_exactly_8_quarters():
    year_ago_quarters = [1.0, 1.1, 1.2, 1.3]  # sums to 4.6
    now_quarters = [1.2, 1.3, 1.4, 1.5]  # sums to 5.4
    fundamentals = _quarterly_fundamentals(
        _eight_quarters(year_ago_quarters + now_quarters)
    )

    result = calculate_ttm_eps_growth_percent(fundamentals)

    assert result == pytest.approx((5.4 / 4.6 - 1) * 100)


def test_ttm_eps_growth_is_none_with_fewer_than_8_quarters():
    fundamentals = _quarterly_fundamentals(
        {
            date(2024, 3, 31): 1.0,
            date(2024, 6, 30): 1.1,
            date(2024, 9, 30): 1.2,
            date(2024, 12, 31): 1.3,
            date(2025, 3, 31): 1.2,
            date(2025, 6, 30): 1.3,
            date(2025, 9, 30): 1.4,
        }
    )
    assert calculate_ttm_eps_growth_percent(fundamentals) is None


def test_ttm_eps_growth_is_none_for_an_annual_period_fetch():
    fundamentals = _annual_fundamentals(
        {
            date(2022, 12, 31): 2.0,
            date(2023, 12, 31): 2.2,
            date(2024, 12, 31): 2.5,
            date(2025, 12, 31): 3.0,
        }
    )
    assert calculate_ttm_eps_growth_percent(fundamentals) is None


def test_ttm_eps_growth_is_none_when_the_year_ago_ttm_window_is_non_positive():
    # A swing from a loss year-ago to a profit now has no meaningful TTM growth
    # rate in this formula, same non-positive-denominator guard as CAGR.
    year_ago_quarters = [-2.0, -0.5, 1.0, 0.5]  # sums to -1.0
    now_quarters = [1.2, 1.3, 1.4, 1.5]
    fundamentals = _quarterly_fundamentals(
        _eight_quarters(year_ago_quarters + now_quarters)
    )
    assert calculate_ttm_eps_growth_percent(fundamentals) is None


def test_ttm_eps_growth_refuses_a_year_ago_match_across_an_interior_gap():
    # Regression: 11 quarterly points with one missing quarter (2025-03-31) in
    # the middle. `ttm_series` skips every 4-quarter window whose span exceeds
    # ~330 days, which leaves TTM points dated 2024-12-31, 2026-03-31,
    # 2026-06-30, 2026-09-30, 2026-12-31 — a naive "5th from the end" position
    # would pair 2026-12-31 against 2024-12-31, a 730-day (two-year) gap, and
    # silently report that as one year of growth. Must refuse instead.
    points = {
        date(2024, 3, 31): 1.0,
        date(2024, 6, 30): 1.0,
        date(2024, 9, 30): 1.0,
        date(2024, 12, 31): 1.0,
        # date(2025, 3, 31) missing
        date(2025, 6, 30): 1.0,
        date(2025, 9, 30): 1.0,
        date(2025, 12, 31): 1.0,
        date(2026, 3, 31): 1.0,
        date(2026, 6, 30): 1.0,
        date(2026, 9, 30): 1.0,
        date(2026, 12, 31): 1.0,
    }
    fundamentals = _quarterly_fundamentals(points)

    assert calculate_ttm_eps_growth_percent(fundamentals) is None


def test_ttm_eps_growth_finds_the_year_ago_point_beyond_the_minimal_8_quarters():
    # 12 consecutive gap-free quarters (more than the minimal 8) — the
    # date-based match must still land on the point exactly 4 quarters back,
    # not just work by coincidence at the minimal-length boundary.
    dates = [
        date(2023, 3, 31),
        date(2023, 6, 30),
        date(2023, 9, 30),
        date(2023, 12, 31),
        date(2024, 3, 31),
        date(2024, 6, 30),
        date(2024, 9, 30),
        date(2024, 12, 31),
        date(2025, 3, 31),
        date(2025, 6, 30),
        date(2025, 9, 30),
        date(2025, 12, 31),
    ]
    values = [1.0, 1.0, 1.0, 1.0, 1.0, 1.1, 1.2, 1.3, 1.2, 1.3, 1.4, 1.5]
    fundamentals = _quarterly_fundamentals(dict(zip(dates, values)))

    result = calculate_ttm_eps_growth_percent(fundamentals)

    # TTM now (quarters ending 2025-03-31..2025-12-31): 1.2+1.3+1.4+1.5 = 5.4
    # TTM year ago (quarters ending 2024-03-31..2024-12-31): 1.0+1.1+1.2+1.3 = 4.6
    assert result == pytest.approx((5.4 / 4.6 - 1) * 100)
