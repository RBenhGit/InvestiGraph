import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from financial_charts.charts.builtins._test_helpers import (
    fundamentals_with,
    ratio_series,
)
from financial_charts.charts.builtins.margins import MarginsChart


def test_declares_gross_and_net_margin_as_required():
    assert MarginsChart().required_metrics == ["gross_margin", "net_margin"]


def test_renders_both_margin_lines_as_percentages():
    fundamentals = fundamentals_with(
        {
            "gross_margin": ratio_series("gross_margin", [0.4, 0.45]),
            "net_margin": ratio_series("net_margin", [0.1, 0.12]),
        }
    )
    fig, ax = plt.subplots()

    MarginsChart().render(ax, fundamentals)

    labels = [line.get_label() for line in ax.get_lines()]
    assert "Gross Margin" in labels
    assert "Net Margin" in labels
    gross_line = next(
        line for line in ax.get_lines() if line.get_label() == "Gross Margin"
    )
    assert list(gross_line.get_ydata()) == [40.0, 45.0]
    plt.close(fig)
