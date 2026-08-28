from matplotlib.axes import Axes

from investigraph.charts.base import render_money_bar
from investigraph.template.models import CompanyFundamentals


class NetIncomeChart:
    name = "net_income"
    title = "Net Income"
    required_metrics = ["net_income"]

    def render(self, ax: Axes, fundamentals: CompanyFundamentals) -> None:
        render_money_bar(ax, fundamentals, "net_income")
