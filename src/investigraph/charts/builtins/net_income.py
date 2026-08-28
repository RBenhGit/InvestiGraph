from matplotlib.axes import Axes

from financial_charts.charts.base import render_money_bar
from financial_charts.template.models import CompanyFundamentals


class NetIncomeChart:
    name = "net_income"
    title = "Net Income"
    required_metrics = ["net_income"]

    def render(self, ax: Axes, fundamentals: CompanyFundamentals) -> None:
        render_money_bar(ax, fundamentals, "net_income")
