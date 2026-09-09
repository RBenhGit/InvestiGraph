from matplotlib.axes import Axes

from investigraph.charts.base import render_money_bar
from investigraph.template.models import CompanyFundamentals, Period


class FreeCashFlowChart:
    name = "free_cash_flow"
    title = "Free Cash Flow"
    required_metrics = ["free_cash_flow"]
    # See docs/UX_NOTES.md — trailing-twelve-month cadence, full available history.
    period = Period.TTM
    range = "max"

    def render(self, ax: Axes, fundamentals: CompanyFundamentals) -> None:
        render_money_bar(ax, fundamentals, "free_cash_flow")
