from datetime import date

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from financial_charts.charts.builtins._test_helpers import (
    fundamentals_with,
    money_series,
)
from financial_charts.charts.builtins.ratios import RatiosChart
from financial_charts.template.models import Currency, MetricSeries, Money, Point, Unit


def test_declares_current_asset_and_liability_metrics_as_required():
    assert RatiosChart().required_metrics == [
        "total_current_assets",
        "total_current_liabilities",
    ]


def test_renders_current_ratio_at_face_value():
    fundamentals = fundamentals_with(
        {
            "total_current_assets": money_series(
                "total_current_assets", [200, 300], scale=Unit.MILLIONS
            ),
            "total_current_liabilities": money_series(
                "total_current_liabilities", [100, 150], scale=Unit.MILLIONS
            ),
        }
    )
    fig, ax = plt.subplots()

    RatiosChart().render(ax, fundamentals)

    line = ax.get_lines()[0]
    assert list(line.get_ydata()) == [2.0, 2.0]
    plt.close(fig)


def test_falls_back_to_no_data_when_dates_do_not_overlap():
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
            "total_current_assets": _single_point_series("total_current_assets", 2020),
            "total_current_liabilities": _single_point_series(
                "total_current_liabilities", 2021
            ),
        }
    )
    fig, ax = plt.subplots()

    RatiosChart().render(ax, fundamentals)

    assert ax.get_lines() == []
    texts = [t.get_text() for t in ax.texts]
    assert "No Data" in texts
    plt.close(fig)
