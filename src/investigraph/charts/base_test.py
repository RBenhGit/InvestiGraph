from datetime import date

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from investigraph.charts.base import (
    currency_label,
    currency_symbol,
    render_or_no_data,
    render_percentage_line,
)
from investigraph.charts.builtins._test_helpers import (
    fundamentals_with,
    money_series,
    ratio_series,
    unavailable_series,
)
from investigraph.charts.builtins.revenue import RevenueChart
from investigraph.template.models import Currency


def test_renders_chart_when_metric_available():
    fundamentals = fundamentals_with(
        {"revenue": money_series("revenue", [1.0, 2.0, 3.0])}
    )
    fig, ax = plt.subplots()

    render_or_no_data(RevenueChart(), ax, fundamentals)

    assert ax.get_title() == "Revenue"
    assert len(ax.patches) > 0  # bars were drawn
    plt.close(fig)


def test_falls_back_to_no_data_when_metric_unavailable():
    fundamentals = fundamentals_with({"revenue": unavailable_series("revenue")})
    fig, ax = plt.subplots()

    render_or_no_data(RevenueChart(), ax, fundamentals)

    assert ax.get_title() == "Revenue"
    assert len(ax.patches) == 0
    texts = [t.get_text() for t in ax.texts]
    assert "No Data" in texts
    plt.close(fig)


def test_falls_back_to_no_data_when_metric_missing_entirely():
    fundamentals = fundamentals_with({})
    fig, ax = plt.subplots()

    render_or_no_data(RevenueChart(), ax, fundamentals)

    texts = [t.get_text() for t in ax.texts]
    assert "No Data" in texts
    plt.close(fig)


def test_currency_symbol_is_shekel_for_ils():
    fundamentals = fundamentals_with({}, currency=Currency.ILS)
    assert currency_symbol(fundamentals) == "₪"


def test_currency_symbol_is_dollar_for_usd():
    fundamentals = fundamentals_with({}, currency=Currency.USD)
    assert currency_symbol(fundamentals) == "$"


def test_render_percentage_line_scales_ratios_to_percent():
    fig, ax = plt.subplots()

    render_percentage_line(
        ax, [date(2020, 1, 1), date(2021, 1, 1)], [0.4, 0.45], "Gross Margin"
    )

    line = ax.get_lines()[0]
    assert line.get_label() == "Gross Margin"
    assert list(line.get_ydata()) == [40.0, 45.0]
    plt.close(fig)


# A TASE ticker can trade in ILS but file its statements in USD (QLTU.TA): the market's
# currency (`fundamentals.currency`) labels the price, not every series. An axis must name
# the currency its own series is denominated in.


def test_currency_label_uses_the_series_own_currency_not_the_markets():
    fundamentals = fundamentals_with(
        {"revenue": money_series("revenue", [1.0, 2.0], currency=Currency.USD)},
        currency=Currency.ILS,
    )

    assert currency_label(fundamentals, "revenue") == "$"


def test_currency_label_matches_the_market_when_the_series_does():
    fundamentals = fundamentals_with(
        {"revenue": money_series("revenue", [1.0], currency=Currency.ILS)},
        currency=Currency.ILS,
    )

    assert currency_label(fundamentals, "revenue") == "₪"


def test_currency_label_says_so_when_paired_series_disagree():
    fundamentals = fundamentals_with(
        {
            "cash_and_equivalents": money_series(
                "cash_and_equivalents", [1.0], currency=Currency.USD
            ),
            "total_debt": money_series("total_debt", [1.0], currency=Currency.ILS),
        },
        currency=Currency.ILS,
    )

    label = currency_label(fundamentals, "cash_and_equivalents", "total_debt")

    assert label == "mixed currencies"


def test_currency_label_falls_back_to_the_market_without_money_values():
    fundamentals = fundamentals_with(
        {"net_margin": ratio_series("net_margin", [0.1])}, currency=Currency.ILS
    )

    assert currency_label(fundamentals, "net_margin") == "₪"
    assert currency_label(fundamentals, "not_a_metric") == "₪"


def test_a_usd_bar_chart_on_an_ils_market_is_labelled_in_dollars():
    fundamentals = fundamentals_with(
        {"revenue": money_series("revenue", [1.0, 2.0], currency=Currency.USD)},
        currency=Currency.ILS,
    )
    fig, ax = plt.subplots()

    render_or_no_data(RevenueChart(), ax, fundamentals)

    assert "$" in ax.get_ylabel()
    assert "₪" not in ax.get_ylabel()
    plt.close(fig)
