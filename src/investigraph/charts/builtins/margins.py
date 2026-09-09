from matplotlib.axes import Axes

from investigraph.charts.base import render_percentage_line
from investigraph.template.derived import OPERATING_MARGIN, resolve
from investigraph.template.models import CompanyFundamentals


class MarginsChart:
    name = "margins"
    title = "Margins"
    required_metrics = ["gross_margin", "net_margin"]

    def render(self, ax: Axes, fundamentals: CompanyFundamentals) -> None:
        for metric_id, label in [
            ("gross_margin", "Gross Margin"),
            ("net_margin", "Net Margin"),
        ]:
            points = fundamentals.series[metric_id].points
            render_percentage_line(
                ax, [p.date for p in points], [p.value for p in points], label
            )

        # Operating margin is derived (ebit / revenue) rather than a source-supplied
        # series like gross/net margin above, so it isn't in `required_metrics` —
        # it degrades to simply not adding its line instead of blanking the whole
        # chart when `ebit` or `revenue` is unavailable for this ticker/source.
        operating_margin = resolve(fundamentals, OPERATING_MARGIN)
        if operating_margin.available:
            render_percentage_line(
                ax,
                [p.date for p in operating_margin.points],
                [p.value for p in operating_margin.points],
                "Operating Margin",
            )

        ax.set_ylabel("Margin (%)")
        ax.legend(fontsize=7, loc="upper left")
