from matplotlib.axes import Axes

from investigraph.charts.base import render_money_bar
from investigraph.template.models import CompanyFundamentals


class EBITDAChart:
    name = "ebitda"
    title = "EBITDA"
    required_metrics = ["ebitda"]

    def render(self, ax: Axes, fundamentals: CompanyFundamentals) -> None:
        render_money_bar(ax, fundamentals, "ebitda")
