from datetime import date

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from financial_charts.charts.builtins._test_helpers import (
    fundamentals_with,
    money_series,
)
from financial_charts.charts.builtins.return_on_equity import ReturnOnEquityChart
from financial_charts.template.models import (
    Currency,
    MetricSeries,
    Money,
    Period,
    Point,
    Unit,
)


def test_declares_net_income_and_total_equity_as_required():
    assert ReturnOnEquityChart().required_metrics == ["net_income", "total_equity"]


def test_title_reflects_trailing_twelve_month_basis():
    assert ReturnOnEquityChart().title == "ROE (TTM)"


def test_renders_ttm_net_income_over_equity_as_a_percentage_line():
    fundamentals = fundamentals_with(
        {
            "net_income": money_series("net_income", [15.0, 30.0]),
            "total_equity": money_series("total_equity", [200.0, 200.0]),
        }
    )
    fig, ax = plt.subplots()

    ReturnOnEquityChart().render(ax, fundamentals)

    # statement cadence: one point per net_income date, as-of equity
    assert len(ax.lines) == 1
    assert list(ax.lines[0].get_ydata()) == [7.5, 15.0]
    plt.close(fig)


def test_falls_back_to_no_data_on_zero_equity():
    fundamentals = fundamentals_with(
        {
            "net_income": money_series("net_income", [15.0]),
            "total_equity": money_series("total_equity", [0.0]),
        }
    )
    fig, ax = plt.subplots()

    ReturnOnEquityChart().render(ax, fundamentals)

    texts = [t.get_text() for t in ax.texts]
    assert "No Data" in texts
    plt.close(fig)


def test_quarterly_ttm_sums_net_income_across_four_quarters():
    quarter_ends = [
        date(2022, 3, 31),
        date(2022, 6, 30),
        date(2022, 9, 30),
        date(2022, 12, 31),
    ]
    net_income = MetricSeries(
        metric_id="net_income",
        points=[
            Point(
                date=d, value=Money(value=5.0, currency=Currency.USD, scale=Unit.ONES)
            )
            for d in quarter_ends
        ],
        available=True,
    )
    total_equity = MetricSeries(
        metric_id="total_equity",
        points=[
            Point(
                date=date(2022, 1, 1),
                value=Money(value=100, currency=Currency.USD, scale=Unit.ONES),
            )
        ],
        available=True,
    )
    fundamentals = fundamentals_with(
        {"net_income": net_income, "total_equity": total_equity},
        period=Period.QUARTERLY,
    )
    fig, ax = plt.subplots()

    ReturnOnEquityChart().render(ax, fundamentals)

    # TTM net income across the 4 quarters = 20, / 100 equity = 20.0%
    assert list(ax.lines[0].get_ydata()) == [20.0]
    plt.close(fig)
