from matplotlib.axes import Axes

from investigraph.charts.base import draw_no_data, render_percentage_line
from investigraph.template.models import CompanyFundamentals, Period
from investigraph.template.trailing import ROE_TTM, resolve_trailing


class ReturnOnEquityChart:
    name = "return_on_equity"
    title = "ROE (TTM)"
    required_metrics = ["net_income", "total_equity"]
    # See docs/UX_NOTES.md — quarterly cadence, full available history. At
    # Period.QUARTERLY, ROE_TTM's ttm=True net_income input now actually
    # sums a rolling trailing 4 quarters via ttm_series, rather than passing
    # through the whole-year figure unchanged — a real improvement for a
    # chart titled "(TTM)".
    period = Period.QUARTERLY
    range = "max"

    def render(self, ax: Axes, fundamentals: CompanyFundamentals) -> None:
        series = resolve_trailing(fundamentals, ROE_TTM)
        if not series.available:
            draw_no_data(ax)
            return
        dates = [p.date for p in series.points]
        values = [p.value for p in series.points]
        render_percentage_line(ax, dates, values, "ROE")
        ax.set_ylabel("ROE (%)")
        ax.legend(fontsize=7, loc="upper left")
