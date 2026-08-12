from datetime import date

from financial_charts.template.models import (
    CompanyFundamentals,
    Currency,
    Market,
    MetricSeries,
    Money,
    Period,
    Point,
    Unit,
)


def money_series(
    metric_id: str,
    values: list[float],
    currency=Currency.USD,
    scale: Unit = Unit.ONES,
) -> MetricSeries:
    points = [
        Point(
            date=date(2020 + i, 1, 1),
            value=Money(value=v, currency=currency, scale=scale),
        )
        for i, v in enumerate(values)
    ]
    return MetricSeries(metric_id=metric_id, points=points, available=True)


def ratio_series(metric_id: str, values: list[float]) -> MetricSeries:
    points = [Point(date=date(2020 + i, 1, 1), value=v) for i, v in enumerate(values)]
    return MetricSeries(metric_id=metric_id, points=points, available=True)


def unavailable_series(metric_id: str) -> MetricSeries:
    return MetricSeries(metric_id=metric_id, points=[], available=False)


def quarterly_money_series(
    metric_id: str,
    values: list[float],
    currency=Currency.USD,
    scale: Unit = Unit.ONES,
) -> MetricSeries:
    """Quarter-end-dated series, ~91 days apart, for exercising TTM rolling sums."""
    quarter_ends = [
        date(2022, 3, 31),
        date(2022, 6, 30),
        date(2022, 9, 30),
        date(2022, 12, 31),
        date(2023, 3, 31),
        date(2023, 6, 30),
        date(2023, 9, 30),
        date(2023, 12, 31),
    ]
    points = [
        Point(
            date=quarter_ends[i],
            value=Money(value=v, currency=currency, scale=scale),
        )
        for i, v in enumerate(values)
    ]
    return MetricSeries(metric_id=metric_id, points=points, available=True)


def fundamentals_with(
    series: dict[str, MetricSeries],
    currency=Currency.USD,
    period: Period = Period.ANNUAL,
) -> CompanyFundamentals:
    return CompanyFundamentals(
        ticker="TEST",
        market=Market.US,
        currency=currency,
        period=period,
        range="5y",
        series=series,
    )
