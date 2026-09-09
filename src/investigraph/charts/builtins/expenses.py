from matplotlib.axes import Axes

from investigraph.charts.base import render_money_line
from investigraph.template.models import CompanyFundamentals, Period


class ExpensesChart:
    name = "expenses"
    title = "Expenses"
    required_metrics = ["research_and_development", "selling_general_administrative"]
    # See docs/UX_NOTES.md — annual cadence, full available history.
    period = Period.ANNUAL
    range = "max"

    def render(self, ax: Axes, fundamentals: CompanyFundamentals) -> None:
        render_money_line(
            ax,
            fundamentals,
            [
                ("research_and_development", "R&D"),
                ("selling_general_administrative", "SG&A"),
            ],
        )
