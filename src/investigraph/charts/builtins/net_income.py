from matplotlib.axes import Axes

from investigraph.charts.base import render_money_bar
from investigraph.template.models import CompanyFundamentals, Period


class NetIncomeChart:
    name = "net_income"
    title = "Net Income"
    required_metrics = ["net_income"]
    # See docs/UX_NOTES.md — annual cadence, full available history.
    period = Period.ANNUAL
    range = "max"

    def render(self, ax: Axes, fundamentals: CompanyFundamentals) -> None:
        render_money_bar(ax, fundamentals, "net_income")
