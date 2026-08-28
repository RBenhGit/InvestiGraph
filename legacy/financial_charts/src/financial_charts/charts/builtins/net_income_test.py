import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from financial_charts.charts.builtins._test_helpers import (
    fundamentals_with,
    money_series,
)
from financial_charts.charts.builtins.net_income import NetIncomeChart


def test_declares_net_income_as_required():
    assert NetIncomeChart().required_metrics == ["net_income"]


def test_renders_bars_for_each_point():
    fundamentals = fundamentals_with(
        {"net_income": money_series("net_income", [1.0, -2.0, 3.0])}
    )
    fig, ax = plt.subplots()

    NetIncomeChart().render(ax, fundamentals)

    assert len(ax.patches) == 3
    plt.close(fig)
