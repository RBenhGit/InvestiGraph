import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from financial_charts.charts.builtins._test_helpers import (
    fundamentals_with,
    money_series,
)
from financial_charts.charts.builtins.price import PriceChart
from financial_charts.template.models import Currency


def test_declares_price_as_required():
    assert PriceChart().required_metrics == ["price"]


def test_renders_close_line_and_available_smas():
    values = [float(i) for i in range(60)]
    fundamentals = fundamentals_with({"price": money_series("price", values)})
    fig, ax = plt.subplots()

    PriceChart().render(ax, fundamentals)

    labels = [line.get_label() for line in ax.get_lines()]
    assert "Close" in labels
    assert "SMA 50" in labels
    assert "SMA 150" not in labels  # fewer than 150 points
    plt.close(fig)


def test_uses_shekel_label_for_ils_currency():
    fundamentals = fundamentals_with(
        {"price": money_series("price", [1.0, 2.0], currency=Currency.ILS)},
        currency=Currency.ILS,
    )
    fig, ax = plt.subplots()

    PriceChart().render(ax, fundamentals)

    assert "₪" in ax.get_ylabel()
    plt.close(fig)
