import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from financial_charts.charts.builtins._test_helpers import (
    fundamentals_with,
    money_series,
)
from financial_charts.charts.builtins.revenue import RevenueChart


def test_declares_revenue_as_required():
    assert RevenueChart().required_metrics == ["revenue"]


def test_renders_bars_for_each_point():
    fundamentals = fundamentals_with(
        {"revenue": money_series("revenue", [1.0, 2.0, 3.0])}
    )
    fig, ax = plt.subplots()

    RevenueChart().render(ax, fundamentals)

    assert len(ax.patches) == 3
    plt.close(fig)
