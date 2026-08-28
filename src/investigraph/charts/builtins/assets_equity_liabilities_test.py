import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from financial_charts.charts.builtins._test_helpers import (
    fundamentals_with,
    money_series,
)
from financial_charts.charts.builtins.assets_equity_liabilities import (
    AssetsEquityLiabilitiesChart,
)


def test_declares_all_three_lines_as_required():
    assert AssetsEquityLiabilitiesChart().required_metrics == [
        "total_assets",
        "total_equity",
        "total_liabilities",
    ]


def test_renders_a_line_per_series():
    fundamentals = fundamentals_with(
        {
            "total_assets": money_series("total_assets", [1.0, 2.0, 3.0]),
            "total_equity": money_series("total_equity", [4.0, 5.0, 6.0]),
            "total_liabilities": money_series("total_liabilities", [7.0, 8.0, 9.0]),
        }
    )
    fig, ax = plt.subplots()

    AssetsEquityLiabilitiesChart().render(ax, fundamentals)

    assert len(ax.lines) == 3
    plt.close(fig)
