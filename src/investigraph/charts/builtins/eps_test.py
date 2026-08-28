import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from financial_charts.charts.builtins._test_helpers import (
    fundamentals_with,
    money_series,
)
from financial_charts.charts.builtins.eps import EPSChart


def test_declares_eps_as_required():
    assert EPSChart().required_metrics == ["eps"]


def test_renders_bars_for_each_point():
    fundamentals = fundamentals_with({"eps": money_series("eps", [1.5, 2.5, 3.5])})
    fig, ax = plt.subplots()

    EPSChart().render(ax, fundamentals)

    assert len(ax.patches) == 3
    plt.close(fig)
