from typing import Protocol

from matplotlib.axes import Axes

from financial_charts.template.models import CompanyFundamentals


class Chart(Protocol):
    name: str
    title: str
    required_metrics: list[str]

    def render(self, ax: Axes, fundamentals: CompanyFundamentals) -> None: ...


def draw_no_data(ax: Axes) -> None:
    """Draw the shared "No Data" placeholder on `ax`.

    Public so a chart whose data is unavailable only after computation (e.g. a
    derived quantity whose inputs don't share any overlapping date) can fall
    back to the same card as a chart with a missing required metric.
    """
    ax.text(
        0.5,
        0.5,
        "No Data",
        ha="center",
        va="center",
        transform=ax.transAxes,
        fontsize=14,
        color="gray",
    )
    ax.set_xticks([])
    ax.set_yticks([])


def render_or_no_data(
    chart: Chart, ax: Axes, fundamentals: CompanyFundamentals
) -> None:
    """Render `chart`, falling back to a "No Data" card if a required metric is unavailable.

    A source's declared gaps are never a crash — the dashboard grid always renders
    the full layout, with unavailable metrics shown as an explicit "No Data" card.
    """
    missing = [
        metric_id
        for metric_id in chart.required_metrics
        if not fundamentals.series.get(metric_id, _UNAVAILABLE).available
    ]
    ax.set_title(chart.title)
    if missing:
        draw_no_data(ax)
        return
    chart.render(ax, fundamentals)


class _Unavailable:
    available = False


_UNAVAILABLE = _Unavailable()


def currency_symbol(fundamentals: CompanyFundamentals) -> str:
    return "₪" if fundamentals.currency.value == "ILS" else "$"


def render_money_bar(
    ax: Axes, fundamentals: CompanyFundamentals, metric_id: str
) -> None:
    """Shared bar-chart rendering for Money-valued metrics (revenue, net income, FCF, EPS)."""
    points = fundamentals.series[metric_id].points
    dates = [p.date for p in points]
    values = [p.value.value for p in points]

    ax.bar(dates, values, width=60, color="steelblue")
    ax.set_ylabel(
        f"{metric_id.replace('_', ' ').title()} ({currency_symbol(fundamentals)})"
    )


def render_ratio_line(
    ax: Axes,
    dates: list,
    values: list[float],
    label: str,
    color: str | None = None,
    markers: bool = True,
) -> None:
    """Shared line-plot rendering for dimensionless ratio metrics (e.g. current ratio,
    debt/equity) — plotted at face value, unlike `render_percentage_line`.

    `markers=False` drops the per-point marker for daily-density series (e.g. a
    price-driven ratio with ~250 points/year), where markers only add noise.
    """
    kwargs = {"color": color} if color else {}
    ax.plot(dates, values, marker="o" if markers else None, label=label, **kwargs)


def render_percentage_line(
    ax: Axes,
    dates: list,
    values: list[float],
    label: str,
    color: str | None = None,
    markers: bool = True,
) -> None:
    """Shared line-plot rendering for ratio-valued metrics (margins, FCF margin).

    `values` are the raw ratios (e.g. 0.4 for 40%); this scales to percent.
    """
    render_ratio_line(ax, dates, [v * 100 for v in values], label, color, markers)


def render_money_line(
    ax: Axes, fundamentals: CompanyFundamentals, series: list[tuple[str, str]]
) -> None:
    """Shared multi-line rendering for related Money-valued metrics (e.g. an
    expense breakdown or a cash-vs-debt comparison).

    Plots via `as_base_units()`, not the raw `.value` — the paired metrics
    are only guaranteed consistent currency *within* each one's own series
    (see `MetricSeries._consistent_money_tagging`), not against each other,
    so two metrics tagged with different scales would otherwise silently
    mis-plot relative to one another.
    """
    for metric_id, label in series:
        points = fundamentals.series[metric_id].points
        ax.plot(
            [p.date for p in points],
            [p.value.as_base_units() for p in points],
            marker="o",
            label=label,
        )
    ax.set_ylabel(f"({currency_symbol(fundamentals)})")
    ax.legend(fontsize=7, loc="upper left")


def render_float_bar(
    ax: Axes, fundamentals: CompanyFundamentals, metric_id: str, ylabel: str
) -> None:
    """Shared bar-chart rendering for plain-float (non-Money) metrics, e.g. share counts."""
    points = fundamentals.series[metric_id].points
    ax.bar(
        [p.date for p in points], [p.value for p in points], width=60, color="steelblue"
    )
    ax.set_ylabel(ylabel)
