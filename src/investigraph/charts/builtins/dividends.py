from matplotlib.axes import Axes

from investigraph.charts.base import render_money_bar
from investigraph.template.models import CompanyFundamentals, Period


class DividendsChart:
    name = "dividends"
    title = "Dividends Paid"
    required_metrics = ["dividends_paid"]
    # See docs/UX_NOTES.md — quarterly cadence, full available history.
    period = Period.QUARTERLY
    range = "max"

    def render(self, ax: Axes, fundamentals: CompanyFundamentals) -> None:
        render_money_bar(ax, fundamentals, "dividends_paid")
