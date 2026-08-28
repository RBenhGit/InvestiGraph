from matplotlib.axes import Axes

from financial_charts.charts.base import draw_no_data, render_percentage_line
from financial_charts.template.derived import FCF_MARGIN, resolve
from financial_charts.template.models import CompanyFundamentals


class FCFMarginChart:
    name = "fcf_margin"
    title = "FCF Margin"
    required_metrics = ["free_cash_flow", "revenue"]

    def render(self, ax: Axes, fundamentals: CompanyFundamentals) -> None:
        series = resolve(fundamentals, FCF_MARGIN)
        if not series.available:
            # Both inputs were individually available but shared no common
            # date (e.g. the income statement and cash flow statement report
            # different period-end dates) — degrade like a missing metric.
            draw_no_data(ax)
            return

        render_percentage_line(
            ax,
            [p.date for p in series.points],
            [p.value for p in series.points],
            "FCF Margin",
            color="darkorange",
        )
        ax.set_ylabel("FCF Margin (%)")
        ax.legend(fontsize=7, loc="upper left")
