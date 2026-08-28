import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from financial_charts.charts.builtins._test_helpers import (
    fundamentals_with,
    money_series,
)
from financial_charts.charts.builtins.free_cash_flow import FreeCashFlowChart


def test_declares_free_cash_flow_as_required():
    assert FreeCashFlowChart().required_metrics == ["free_cash_flow"]


def test_renders_bars_for_each_point():
    fundamentals = fundamentals_with(
        {"free_cash_flow": money_series("free_cash_flow", [1.0, 2.0, 3.0])}
    )
    fig, ax = plt.subplots()

    FreeCashFlowChart().render(ax, fundamentals)

    assert len(ax.patches) == 3
    plt.close(fig)
