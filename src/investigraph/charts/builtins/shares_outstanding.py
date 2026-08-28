from matplotlib.axes import Axes

from financial_charts.charts.base import render_float_bar
from financial_charts.template.models import CompanyFundamentals


class SharesOutstandingChart:
    name = "shares_outstanding"
    title = "Shares Outstanding"
    required_metrics = ["shares_outstanding"]

    def render(self, ax: Axes, fundamentals: CompanyFundamentals) -> None:
        render_float_bar(ax, fundamentals, "shares_outstanding", "Shares")
