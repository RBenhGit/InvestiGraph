from matplotlib.axes import Axes

from financial_charts.charts.base import render_money_bar
from financial_charts.template.models import CompanyFundamentals


class FreeCashFlowChart:
    name = "free_cash_flow"
    title = "Free Cash Flow"
    required_metrics = ["free_cash_flow"]

    def render(self, ax: Axes, fundamentals: CompanyFundamentals) -> None:
        render_money_bar(ax, fundamentals, "free_cash_flow")
