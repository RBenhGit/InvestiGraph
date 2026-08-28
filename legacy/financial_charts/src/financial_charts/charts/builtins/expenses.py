from matplotlib.axes import Axes

from financial_charts.charts.base import render_money_line
from financial_charts.template.models import CompanyFundamentals


class ExpensesChart:
    name = "expenses"
    title = "Expenses"
    required_metrics = ["research_and_development", "selling_general_administrative"]

    def render(self, ax: Axes, fundamentals: CompanyFundamentals) -> None:
        render_money_line(
            ax,
            fundamentals,
            [
                ("research_and_development", "R&D"),
                ("selling_general_administrative", "SG&A"),
            ],
        )
