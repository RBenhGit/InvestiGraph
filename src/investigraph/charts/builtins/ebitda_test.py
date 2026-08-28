import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from investigraph.charts.builtins._test_helpers import (
    fundamentals_with,
    money_series,
)
from investigraph.charts.builtins.ebitda import EBITDAChart


def test_declares_ebitda_as_required():
    assert EBITDAChart().required_metrics == ["ebitda"]


def test_renders_bars_for_each_point():
    fundamentals = fundamentals_with(
        {"ebitda": money_series("ebitda", [1.0, 2.0, 3.0])}
    )
    fig, ax = plt.subplots()

    EBITDAChart().render(ax, fundamentals)

    assert len(ax.patches) == 3
    plt.close(fig)
