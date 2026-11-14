from datetime import date

import pytest

from investigraph.sources.base import SourceUnavailable
from investigraph.sources.ttm import build_ttm_fundamentals
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
from investigraph.template.trailing import derive_ttm_fundamentals

# QLTU.TA's real EPS: the source omits Q4 2025, so a TTM built from the quarters alone is empty.
_QUARTERS = [
    (date(2025, 3, 31), 1.227),
    (date(2025, 6, 30), 1.398),
    (date(2025, 9, 30), 2.315),
    (date(2026, 3, 31), 0.609),
    (date(2026, 6, 30), 2.135),
]
_ANNUAL = [
    (date(2023, 12, 31), 2.688),
    (date(2024, 12, 31), 3.017),
    (date(2025, 12, 31), 4.676),
]


def _fundamentals(period: Period, eps: list[tuple[date, float]]) -> CompanyFundamentals:
    return CompanyFundamentals(
        ticker="QLTU.TA",
        market=Market.TASE,
        currency=Currency.ILS,
        period=period,
        range="max",
        series={
            "eps": MetricSeries(
                metric_id="eps",
                points=[
                    Point(
                        date=d,
                        value=Money(value=v, currency=Currency.USD, scale=Unit.ONES),
                    )
                    for d, v in eps
                ],
                available=True,
            ),
            # Point-in-time metrics must come from the QUARTERLY series, never the annual one.
            "total_assets": MetricSeries(
                metric_id="total_assets",
                points=[
                    Point(
                        date=date(2026, 6, 30),
                        value=Money(
                            value=777.0, currency=Currency.USD, scale=Unit.ONES
                        ),
                    )
                ],
                available=True,
            ),
        },
    )


class _Source:
    """Stands in for a cache-aware loader: records which periods were asked for."""

    def __init__(self, annual_error: Exception | None = None):
        self.calls: list[Period] = []
        self._annual_error = annual_error

    def __call__(self, period: Period) -> CompanyFundamentals:
        self.calls.append(period)
        if period == Period.ANNUAL:
            if self._annual_error:
                raise self._annual_error
            return _fundamentals(Period.ANNUAL, _ANNUAL)
        if period == Period.QUARTERLY:
            return _fundamentals(Period.QUARTERLY, _QUARTERS)
        raise AssertionError(
            f"TTM must be built from QUARTERLY + ANNUAL, asked for {period}"
        )


def _eps(fundamentals: CompanyFundamentals) -> dict[date, float]:
    return {p.date: p.value.value for p in fundamentals.series["eps"].points}


def test_builds_ttm_from_one_quarterly_and_one_annual_series_and_never_asks_for_ttm():
    source = _Source()

    result = build_ttm_fundamentals(source)

    assert result.period == Period.TTM
    assert source.calls == [Period.QUARTERLY, Period.ANNUAL]


def test_result_is_identical_to_deriving_it_directly_from_the_same_two_series():
    # The saving must not change the data: same inputs, same function, same output.
    expected = derive_ttm_fundamentals(
        _fundamentals(Period.QUARTERLY, _QUARTERS),
        annual_loader=lambda: _fundamentals(Period.ANNUAL, _ANNUAL),
    )

    result = build_ttm_fundamentals(_Source())

    assert result.model_dump() == expected.model_dump()


def test_uses_the_annual_series_for_the_missing_quarter_and_older_year_ends():
    eps = _eps(build_ttm_fundamentals(_Source()))

    assert eps[date(2025, 12, 31)] == pytest.approx(4.676)
    assert eps[date(2026, 6, 30)] == pytest.approx(4.795)
    assert (
        eps[date(2023, 12, 31)] == 2.688
    )  # fiscal-year-end point from the annual series


def test_point_in_time_metrics_still_come_from_the_quarterly_series():
    result = build_ttm_fundamentals(_Source())

    [point] = result.series["total_assets"].points
    assert point.value.value == 777.0 and point.date == date(2026, 6, 30)


def test_an_unavailable_annual_fetch_degrades_to_a_quarterly_only_ttm_with_a_note():
    result = build_ttm_fundamentals(
        _Source(annual_error=SourceUnavailable("no credits"))
    )

    assert result.period == Period.TTM
    assert result.series["eps"].available is False  # the gap could not be filled
    assert any("could not be reconstructed" in limit for limit in result.source_limits)


def test_an_unavailable_quarterly_fetch_is_not_swallowed():
    def fetch(period):
        raise SourceUnavailable("down")

    with pytest.raises(SourceUnavailable):
        build_ttm_fundamentals(fetch)
