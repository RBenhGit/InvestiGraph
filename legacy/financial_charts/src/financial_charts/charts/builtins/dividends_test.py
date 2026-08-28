import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from financial_charts.charts.builtins._test_helpers import (
    fundamentals_with,
    money_series,
)
from financial_charts.charts.builtins.dividends import DividendsChart


def test_declares_dividends_paid_as_required():
    assert DividendsChart().required_metrics == ["dividends_paid"]


def test_renders_bars_for_each_point():
    fundamentals = fundamentals_with(
        {"dividends_paid": money_series("dividends_paid", [1.0, 2.0, 3.0])}
    )
    fig, ax = plt.subplots()

    DividendsChart().render(ax, fundamentals)

    assert len(ax.patches) == 3
    plt.close(fig)
