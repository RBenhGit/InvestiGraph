from matplotlib.axes import Axes

from financial_charts.charts.base import render_money_bar
from financial_charts.template.models import CompanyFundamentals


class RevenueChart:
    name = "revenue"
    title = "Revenue"
    required_metrics = ["revenue"]

    def render(self, ax: Axes, fundamentals: CompanyFundamentals) -> None:
        render_money_bar(ax, fundamentals, "revenue")
