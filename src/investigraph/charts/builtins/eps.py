from matplotlib.axes import Axes

from investigraph.charts.base import render_money_bar
from investigraph.template.models import CompanyFundamentals, Period


class EPSChart:
    name = "eps"
    title = "EPS (Diluted)"
    required_metrics = ["eps"]
    # See docs/UX_NOTES.md — trailing-twelve-month cadence, full available history.
    period = Period.TTM
    range = "max"

    def render(self, ax: Axes, fundamentals: CompanyFundamentals) -> None:
        render_money_bar(ax, fundamentals, "eps")
