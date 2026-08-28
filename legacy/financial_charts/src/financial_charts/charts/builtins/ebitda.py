from matplotlib.axes import Axes

from financial_charts.charts.base import render_money_bar
from financial_charts.template.models import CompanyFundamentals


class EBITDAChart:
    name = "ebitda"
    title = "EBITDA"
    required_metrics = ["ebitda"]

    def render(self, ax: Axes, fundamentals: CompanyFundamentals) -> None:
        render_money_bar(ax, fundamentals, "ebitda")
