import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from financial_charts.charts.builtins._test_helpers import (
    fundamentals_with,
    ratio_series,
)
from financial_charts.charts.builtins.shares_outstanding import SharesOutstandingChart


def test_declares_shares_outstanding_as_required():
    assert SharesOutstandingChart().required_metrics == ["shares_outstanding"]


def test_renders_bars_for_each_point():
    fundamentals = fundamentals_with(
        {"shares_outstanding": ratio_series("shares_outstanding", [1.0, 2.0, 3.0])}
    )
    fig, ax = plt.subplots()

    SharesOutstandingChart().render(ax, fundamentals)

    assert len(ax.patches) == 3
    plt.close(fig)
