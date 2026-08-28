from matplotlib.axes import Axes

from investigraph.charts.base import render_money_bar
from investigraph.template.models import CompanyFundamentals


class DividendsChart:
    name = "dividends"
    title = "Dividends Paid"
    required_metrics = ["dividends_paid"]

    def render(self, ax: Axes, fundamentals: CompanyFundamentals) -> None:
        render_money_bar(ax, fundamentals, "dividends_paid")
