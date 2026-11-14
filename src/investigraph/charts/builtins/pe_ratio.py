import math

from matplotlib.axes import Axes

from investigraph.charts.base import draw_no_data, render_ratio_line
from investigraph.template.models import CompanyFundamentals, Period
from investigraph.template.trailing import pe_ratio_metric, resolve_trailing


class PERatioChart:
    name = "pe_ratio"
    title = "P/E (TTM)"
    required_metrics = ["price", "eps"]
    # Price-driven; see PriceChart's period/range comment (docs/UX_NOTES.md's
    # "keep as-is" group). At Period.ANNUAL, PE_RATIO_TTM's ttm=True eps input
    # passes through ttm_series as an identity (it only sums under
    # Period.QUARTERLY) — same behavior as before this change, since annual
    # EPS is already a 12-month total.
    period = Period.ANNUAL
    range = "10y"

    def render(self, ax: Axes, fundamentals: CompanyFundamentals) -> None:
        series = resolve_trailing(fundamentals, pe_ratio_metric(fundamentals))
        if not series.available:
            draw_no_data(ax)
            return
        dates = [p.date for p in series.points]
        values = [p.value for p in series.points]
        render_ratio_line(ax, dates, values, "P/E", markers=False)

        valid = [v for v in values if not math.isnan(v)]
        if valid:
            average = sum(valid) / len(valid)
            ax.axhline(
                average,
                color="gray",
                linestyle="--",
                linewidth=1,
                label=f"Avg {average:.1f}x",
            )

        ax.set_ylabel("P/E (x)")
        ax.legend(fontsize=7, loc="upper left")
