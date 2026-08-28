from matplotlib.axes import Axes

from investigraph.charts.base import render_money_bar
from investigraph.template.models import CompanyFundamentals


class RevenueChart:
    name = "revenue"
    title = "Revenue"
    required_metrics = ["revenue"]

    def render(self, ax: Axes, fundamentals: CompanyFundamentals) -> None:
        render_money_bar(ax, fundamentals, "revenue")
