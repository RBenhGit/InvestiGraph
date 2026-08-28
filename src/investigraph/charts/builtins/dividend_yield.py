from matplotlib.axes import Axes

from financial_charts.charts.base import draw_no_data, render_percentage_line
from financial_charts.template.models import CompanyFundamentals
from financial_charts.template.trailing import DIVIDEND_YIELD_TTM, resolve_trailing


class DividendYieldChart:
    name = "dividend_yield"
    title = "Dividend Yield (TTM)"
    required_metrics = ["price", "dividends_paid", "shares_outstanding"]

    def render(self, ax: Axes, fundamentals: CompanyFundamentals) -> None:
        series = resolve_trailing(fundamentals, DIVIDEND_YIELD_TTM)
        if not series.available:
            draw_no_data(ax)
            return
        dates = [p.date for p in series.points]
        values = [p.value for p in series.points]
        render_percentage_line(ax, dates, values, "Dividend Yield", markers=False)
        ax.set_ylabel("Dividend Yield (%)")
        ax.legend(fontsize=7, loc="upper left")
