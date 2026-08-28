from datetime import date

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from financial_charts.charts.builtins._test_helpers import (
    fundamentals_with,
    money_series,
)
from financial_charts.charts.builtins.return_on_capital import ReturnOnCapitalChart
from financial_charts.template.models import Currency, MetricSeries, Money, Point, Unit


def test_declares_all_seven_roic_roce_inputs_as_required():
    assert ReturnOnCapitalChart().required_metrics == [
        "ebit",
        "total_assets",
        "total_current_liabilities",
        "net_income",
        "total_debt",
        "total_equity",
        "cash_and_equivalents",
    ]


def test_renders_both_roce_and_roic_as_percentages():
    fundamentals = fundamentals_with(
        {
            "ebit": money_series("ebit", [20], scale=Unit.MILLIONS),
            "total_assets": money_series("total_assets", [300], scale=Unit.MILLIONS),
            "total_current_liabilities": money_series(
                "total_current_liabilities", [100], scale=Unit.MILLIONS
            ),
            "net_income": money_series("net_income", [15], scale=Unit.MILLIONS),
            "total_debt": money_series("total_debt", [50], scale=Unit.MILLIONS),
            "total_equity": money_series("total_equity", [200], scale=Unit.MILLIONS),
            "cash_and_equivalents": money_series(
                "cash_and_equivalents", [50], scale=Unit.MILLIONS
            ),
        }
    )
    fig, ax = plt.subplots()

    ReturnOnCapitalChart().render(ax, fundamentals)

    assert len(ax.lines) == 2
    roce_line, roic_line = ax.lines
    assert list(roce_line.get_ydata()) == [10.0]
    assert list(roic_line.get_ydata()) == [7.5]
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
            "ebit": _single_point_series("ebit", 2020),
            "total_assets": _single_point_series("total_assets", 2020),
            "total_current_liabilities": _single_point_series(
                "total_current_liabilities", 2021
            ),
            "net_income": _single_point_series("net_income", 2020),
            "total_debt": _single_point_series("total_debt", 2020),
            "total_equity": _single_point_series("total_equity", 2020),
            "cash_and_equivalents": _single_point_series("cash_and_equivalents", 2020),
        }
    )
    fig, ax = plt.subplots()

    ReturnOnCapitalChart().render(ax, fundamentals)

    assert ax.get_lines() == []
    texts = [t.get_text() for t in ax.texts]
    assert "No Data" in texts
    plt.close(fig)
