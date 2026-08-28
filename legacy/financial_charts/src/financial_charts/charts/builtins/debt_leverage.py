from matplotlib.axes import Axes

from financial_charts.charts.base import draw_no_data, render_ratio_line
from financial_charts.template.derived import DEBT_TO_EQUITY, resolve
from financial_charts.template.models import CompanyFundamentals


class DebtLeverageChart:
    name = "debt_leverage"
    title = "Debt / Financial Leverage"
    required_metrics = ["total_debt", "total_equity"]

    def render(self, ax: Axes, fundamentals: CompanyFundamentals) -> None:
        series = resolve(fundamentals, DEBT_TO_EQUITY)
        if not series.available:
            # Both inputs were individually available but shared no common
            # date — degrade like a missing metric.
            draw_no_data(ax)
            return

        render_ratio_line(
            ax,
            [p.date for p in series.points],
            [p.value for p in series.points],
            "Debt / Equity",
            color="firebrick",
        )
        ax.set_ylabel("Debt / Equity (x)")
        ax.legend(fontsize=7, loc="upper left")
