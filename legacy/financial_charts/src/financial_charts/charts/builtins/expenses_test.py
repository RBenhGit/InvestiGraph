import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from financial_charts.charts.builtins._test_helpers import (
    fundamentals_with,
    money_series,
)
from financial_charts.charts.builtins.expenses import ExpensesChart


def test_declares_both_expense_lines_as_required():
    assert ExpensesChart().required_metrics == [
        "research_and_development",
        "selling_general_administrative",
    ]


def test_renders_a_line_per_expense_series():
    fundamentals = fundamentals_with(
        {
            "research_and_development": money_series(
                "research_and_development", [1.0, 2.0, 3.0]
            ),
            "selling_general_administrative": money_series(
                "selling_general_administrative", [4.0, 5.0, 6.0]
            ),
        }
    )
    fig, ax = plt.subplots()

    ExpensesChart().render(ax, fundamentals)

    assert len(ax.lines) == 2
    plt.close(fig)
