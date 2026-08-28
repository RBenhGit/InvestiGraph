from datetime import date

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from financial_charts.charts.builtins._test_helpers import (
    fundamentals_with,
    money_series,
)
from financial_charts.charts.builtins.debt_leverage import DebtLeverageChart
from financial_charts.template.models import Currency, MetricSeries, Money, Point, Unit


def test_declares_total_debt_and_equity_as_required():
    assert DebtLeverageChart().required_metrics == ["total_debt", "total_equity"]


def test_renders_debt_to_equity_at_face_value():
    fundamentals = fundamentals_with(
        {
            "total_debt": money_series("total_debt", [50, 75], scale=Unit.MILLIONS),
            "total_equity": money_series(
                "total_equity", [200, 150], scale=Unit.MILLIONS
            ),
        }
    )
    fig, ax = plt.subplots()

    DebtLeverageChart().render(ax, fundamentals)

    line = ax.get_lines()[0]
    assert list(line.get_ydata()) == [0.25, 0.5]
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
            "total_debt": _single_point_series("total_debt", 2020),
            "total_equity": _single_point_series("total_equity", 2021),
        }
    )
    fig, ax = plt.subplots()

    DebtLeverageChart().render(ax, fundamentals)

    assert ax.get_lines() == []
    texts = [t.get_text() for t in ax.texts]
    assert "No Data" in texts
    plt.close(fig)
