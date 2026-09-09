import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from investigraph.charts.builtins._test_helpers import (
    fundamentals_with,
    money_series,
    ratio_series,
)
from investigraph.charts.builtins.margins import MarginsChart


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


def test_renders_operating_margin_line_when_ebit_and_revenue_available():
    fundamentals = fundamentals_with(
        {
            "gross_margin": ratio_series("gross_margin", [0.4]),
            "net_margin": ratio_series("net_margin", [0.1]),
            "ebit": money_series("ebit", [30]),
            "revenue": money_series("revenue", [200]),
        }
    )
    fig, ax = plt.subplots()

    MarginsChart().render(ax, fundamentals)

    labels = [line.get_label() for line in ax.get_lines()]
    assert "Operating Margin" in labels
    operating_line = next(
        line for line in ax.get_lines() if line.get_label() == "Operating Margin"
    )
    assert list(operating_line.get_ydata()) == [15.0]
    plt.close(fig)


def test_omits_operating_margin_line_when_ebit_unavailable():
    fundamentals = fundamentals_with(
        {
            "gross_margin": ratio_series("gross_margin", [0.4]),
            "net_margin": ratio_series("net_margin", [0.1]),
        }
    )
    fig, ax = plt.subplots()

    MarginsChart().render(ax, fundamentals)

    labels = [line.get_label() for line in ax.get_lines()]
    assert "Operating Margin" not in labels
    plt.close(fig)
