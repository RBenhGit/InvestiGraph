from matplotlib.axes import Axes

from investigraph.charts.base import render_money_line
from investigraph.template.models import CompanyFundamentals, Period


class AssetsEquityLiabilitiesChart:
    name = "assets_equity_liabilities"
    title = "Assets / Equity / Liabilities"
    required_metrics = ["total_assets", "total_equity", "total_liabilities"]
    # See docs/UX_NOTES.md — quarterly cadence, full available history.
    period = Period.QUARTERLY
    range = "max"

    def render(self, ax: Axes, fundamentals: CompanyFundamentals) -> None:
        render_money_line(
            ax,
            fundamentals,
            [
                ("total_assets", "Assets"),
                ("total_equity", "Equity"),
                ("total_liabilities", "Liabilities"),
            ],
        )
