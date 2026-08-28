from matplotlib.axes import Axes

from financial_charts.charts.base import draw_no_data, render_percentage_line
from financial_charts.template.derived import ROCE, ROIC, resolve
from financial_charts.template.models import CompanyFundamentals


class ReturnOnCapitalChart:
    name = "return_on_capital"
    title = "Return on Capital (ROIC/ROCE)"
    required_metrics = [
        "ebit",
        "total_assets",
        "total_current_liabilities",
        "net_income",
        "total_debt",
        "total_equity",
        "cash_and_equivalents",
    ]

    def render(self, ax: Axes, fundamentals: CompanyFundamentals) -> None:
        roce_series = resolve(fundamentals, ROCE)
        roic_series = resolve(fundamentals, ROIC)
        if not roce_series.available or not roic_series.available:
            # Every input was individually available but one of the two
            # derived quantities shared no common date across its inputs —
            # degrade like a missing metric.
            draw_no_data(ax)
            return

        render_percentage_line(
            ax,
            [p.date for p in roce_series.points],
            [p.value for p in roce_series.points],
            "ROCE",
        )
        render_percentage_line(
            ax,
            [p.date for p in roic_series.points],
            [p.value for p in roic_series.points],
            "ROIC",
        )
        ax.set_ylabel("Return (%)")
        ax.legend(fontsize=7, loc="upper left")
