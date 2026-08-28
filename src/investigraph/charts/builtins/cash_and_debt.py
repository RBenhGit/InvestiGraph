from matplotlib.axes import Axes

from investigraph.charts.base import render_money_line
from investigraph.template.models import CompanyFundamentals


class CashAndDebtChart:
    name = "cash_and_debt"
    title = "Cash & Debt"
    required_metrics = ["cash_and_equivalents", "total_debt"]

    def render(self, ax: Axes, fundamentals: CompanyFundamentals) -> None:
        render_money_line(
            ax,
            fundamentals,
            [
                ("cash_and_equivalents", "Cash"),
                ("total_debt", "Total Debt"),
            ],
        )
