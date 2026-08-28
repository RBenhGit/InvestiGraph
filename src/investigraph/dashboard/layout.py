import base64
import io
import math

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from financial_charts.charts.base import render_or_no_data
from financial_charts.charts.registry import get_chart_set
from financial_charts.template.models import CompanyFundamentals

_GRID_COLUMNS = 2
_CARD_FIGSIZE = (5, 3.2)


class ChartCard:
    def __init__(self, title: str, png_base64: str):
        self.title = title
        self.png_base64 = png_base64


def render_chart_cards(
    fundamentals: CompanyFundamentals, chart_set_name: str
) -> list[ChartCard]:
    """Render each chart in the named set to its own PNG, for the HTML card grid."""
    cards = []
    for chart in get_chart_set(chart_set_name):
        fig, ax = plt.subplots(figsize=_CARD_FIGSIZE)
        render_or_no_data(chart, ax, fundamentals)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=110)
        plt.close(fig)
        cards.append(
            ChartCard(
                title=chart.title,
                png_base64=base64.b64encode(buf.getvalue()).decode("ascii"),
            )
        )
    return cards


def render_grid_figure(
    fundamentals: CompanyFundamentals, chart_set_name: str
) -> Figure:
    """Compose the named chart set into a single matplotlib grid, for PNG/PDF export."""
    charts = get_chart_set(chart_set_name)
    nrows = math.ceil(len(charts) / _GRID_COLUMNS)
    fig, axes = plt.subplots(
        nrows, _GRID_COLUMNS, figsize=(11, 3.2 * nrows), squeeze=False
    )
    axes_flat = axes.flatten()

    for ax, chart in zip(axes_flat, charts):
        render_or_no_data(chart, ax, fundamentals)
    for ax in axes_flat[len(charts) :]:
        ax.axis("off")

    fig.suptitle(f"{fundamentals.ticker} — {chart_set_name}")
    fig.tight_layout()
    return fig
