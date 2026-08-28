from matplotlib.axes import Axes

from financial_charts.charts.base import draw_no_data, render_ratio_line
from financial_charts.template.derived import CURRENT_RATIO, resolve
from financial_charts.template.models import CompanyFundamentals


class RatiosChart:
    name = "ratios"
    title = "Current Ratio"
    required_metrics = ["total_current_assets", "total_current_liabilities"]

    def render(self, ax: Axes, fundamentals: CompanyFundamentals) -> None:
        series = resolve(fundamentals, CURRENT_RATIO)
        if not series.available:
            # Both inputs were individually available but shared no common
            # date — degrade like a missing metric.
            draw_no_data(ax)
            return

        render_ratio_line(
            ax,
            [p.date for p in series.points],
            [p.value for p in series.points],
            "Current Ratio",
            color="seagreen",
        )
        ax.set_ylabel("Current Ratio (x)")
        ax.legend(fontsize=7, loc="upper left")
