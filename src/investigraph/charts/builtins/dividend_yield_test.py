from datetime import date

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from financial_charts.charts.builtins._test_helpers import (
    fundamentals_with,
    money_series,
    ratio_series,
)
from financial_charts.charts.builtins.dividend_yield import DividendYieldChart
from financial_charts.template.models import (
    Currency,
    MetricSeries,
    Money,
    Period,
    Point,
    Unit,
)


def test_declares_price_dividends_and_shares_as_required():
    assert DividendYieldChart().required_metrics == [
        "price",
        "dividends_paid",
        "shares_outstanding",
    ]


def test_title_reflects_trailing_twelve_month_basis():
    assert DividendYieldChart().title == "Dividend Yield (TTM)"


def test_renders_ttm_dividend_per_share_over_price_as_a_percentage_line():
    fundamentals = fundamentals_with(
        {
            "price": money_series("price", [100.0]),
            "dividends_paid": money_series("dividends_paid", [200_000.0]),
            "shares_outstanding": ratio_series("shares_outstanding", [100_000.0]),
        }
    )
    fig, ax = plt.subplots()

    DividendYieldChart().render(ax, fundamentals)

    # dividend/share = $2; yield = 2/100 = 2.00%
    assert len(ax.lines) == 1
    assert list(ax.lines[0].get_ydata()) == [2.0]
    plt.close(fig)


def test_falls_back_to_no_data_on_currency_mismatch():
    # A dual-listed company can report financials in a different currency
    # than the one its shares trade in — must degrade, never silently
    # combine mismatched currencies into a nonsensical yield.
    fundamentals = fundamentals_with(
        {
            "price": money_series("price", [100.0], currency=Currency.ILS),
            "dividends_paid": money_series(
                "dividends_paid", [200_000.0], currency=Currency.USD
            ),
            "shares_outstanding": ratio_series("shares_outstanding", [100_000.0]),
        }
    )
    fig, ax = plt.subplots()

    DividendYieldChart().render(ax, fundamentals)

    texts = [t.get_text() for t in ax.texts]
    assert "No Data" in texts
    plt.close(fig)


def test_falls_back_to_no_data_on_zero_price():
    fundamentals = fundamentals_with(
        {
            "price": money_series("price", [0.0]),
            "dividends_paid": money_series("dividends_paid", [200_000.0]),
            "shares_outstanding": ratio_series("shares_outstanding", [100_000.0]),
        }
    )
    fig, ax = plt.subplots()

    DividendYieldChart().render(ax, fundamentals)

    texts = [t.get_text() for t in ax.texts]
    assert "No Data" in texts
    plt.close(fig)


def test_quarterly_ttm_sums_dividends_across_four_quarters():
    quarter_ends = [
        date(2022, 3, 31),
        date(2022, 6, 30),
        date(2022, 9, 30),
        date(2022, 12, 31),
    ]
    dividends = MetricSeries(
        metric_id="dividends_paid",
        points=[
            Point(
                date=d, value=Money(value=10.0, currency=Currency.USD, scale=Unit.ONES)
            )
            for d in quarter_ends
        ],
        available=True,
    )
    price = MetricSeries(
        metric_id="price",
        points=[
            Point(
                date=date(2022, 12, 31),
                value=Money(value=100, currency=Currency.USD, scale=Unit.ONES),
            )
        ],
        available=True,
    )
    fundamentals = fundamentals_with(
        {
            "price": price,
            "dividends_paid": dividends,
            "shares_outstanding": ratio_series("shares_outstanding", [40.0]),
        },
        period=Period.QUARTERLY,
    )
    fig, ax = plt.subplots()

    DividendYieldChart().render(ax, fundamentals)

    # TTM dividends = 40, / 40 shares = $1/share, / $100 price = 1.00%
    assert list(ax.lines[0].get_ydata()) == [1.0]
    plt.close(fig)
