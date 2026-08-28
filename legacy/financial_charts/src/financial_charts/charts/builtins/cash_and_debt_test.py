import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from financial_charts.charts.builtins._test_helpers import (
    fundamentals_with,
    money_series,
)
from financial_charts.charts.builtins.cash_and_debt import CashAndDebtChart


def test_declares_cash_and_debt_as_required():
    assert CashAndDebtChart().required_metrics == [
        "cash_and_equivalents",
        "total_debt",
    ]


def test_renders_a_line_per_series():
    fundamentals = fundamentals_with(
        {
            "cash_and_equivalents": money_series(
                "cash_and_equivalents", [1.0, 2.0, 3.0]
            ),
            "total_debt": money_series("total_debt", [4.0, 5.0, 6.0]),
        }
    )
    fig, ax = plt.subplots()

    CashAndDebtChart().render(ax, fundamentals)

    assert len(ax.lines) == 2
    plt.close(fig)
