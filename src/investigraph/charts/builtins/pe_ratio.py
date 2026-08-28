from matplotlib.axes import Axes

from investigraph.charts.base import draw_no_data, render_ratio_line
from investigraph.template.models import CompanyFundamentals
from investigraph.template.trailing import PE_RATIO_TTM, resolve_trailing


class PERatioChart:
    name = "pe_ratio"
    title = "P/E (TTM)"
    required_metrics = ["price", "eps"]

    def render(self, ax: Axes, fundamentals: CompanyFundamentals) -> None:
        series = resolve_trailing(fundamentals, PE_RATIO_TTM)
        if not series.available:
            draw_no_data(ax)
            return
        dates = [p.date for p in series.points]
        values = [p.value for p in series.points]
        render_ratio_line(ax, dates, values, "P/E", markers=False)
        ax.set_ylabel("P/E (x)")
        ax.legend(fontsize=7, loc="upper left")
