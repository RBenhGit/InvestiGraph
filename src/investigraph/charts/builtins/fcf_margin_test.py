from datetime import date

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from financial_charts.charts.builtins._test_helpers import (
    fundamentals_with,
    money_series,
)
from financial_charts.charts.builtins.fcf_margin import FCFMarginChart
from financial_charts.template.models import Currency, MetricSeries, Money, Point, Unit


def test_declares_free_cash_flow_and_revenue_as_required():
    assert FCFMarginChart().required_metrics == ["free_cash_flow", "revenue"]


def test_renders_fcf_margin_as_a_percentage():
    fundamentals = fundamentals_with(
        {
            "free_cash_flow": money_series(
                "free_cash_flow", [100, 150], scale=Unit.MILLIONS
            ),
            "revenue": money_series("revenue", [1000, 1000], scale=Unit.MILLIONS),
        }
    )
    fig, ax = plt.subplots()

    FCFMarginChart().render(ax, fundamentals)

    line = ax.get_lines()[0]
    assert list(line.get_ydata()) == [10.0, 15.0]
    plt.close(fig)


def test_falls_back_to_no_data_when_dates_do_not_overlap():
    # required_metrics gates rendering on the raw availability flag, not on
    # date overlap — free_cash_flow and revenue can each be individually
    # "available" (e.g. from separate income-statement / cash-flow endpoints)
    # yet share no common reporting date. That must degrade to "No Data" like
    # any other gap, not silently draw a blank chart.
    def _single_point_series(metric_id: str, year: int) -> MetricSeries:
        return MetricSeries(
            metric_id=metric_id,
            points=[
                Point(
                    date=date(year, 1, 1),
                    value=Money(value=100, currency=Currency.USD, scale=Unit.ONES),
                )
            ],
            available=True,
        )

    fundamentals = fundamentals_with(
        {
            "free_cash_flow": _single_point_series("free_cash_flow", 2020),
            "revenue": _single_point_series("revenue", 2021),
        }
    )
    fig, ax = plt.subplots()

    FCFMarginChart().render(ax, fundamentals)

    assert ax.get_lines() == []
    texts = [t.get_text() for t in ax.texts]
    assert "No Data" in texts
    plt.close(fig)
