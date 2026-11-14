from matplotlib.axes import Axes

from investigraph.charts.base import render_float_bar
from investigraph.template.models import CompanyFundamentals, Period


class SharesOutstandingChart:
    name = "shares_outstanding"
    title = "Shares Outstanding"
    required_metrics = ["shares_outstanding"]
    # See docs/UX_NOTES.md — quarterly cadence, full available history.
    period = Period.QUARTERLY
    range = "max"

    def render(self, ax: Axes, fundamentals: CompanyFundamentals) -> None:
        render_float_bar(ax, fundamentals, "shares_outstanding", "Shares")
