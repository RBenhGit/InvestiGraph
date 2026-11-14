from typing import Protocol

from matplotlib.axes import Axes

from investigraph.template.models import CompanyFundamentals, Currency, Money, Period


class Chart(Protocol):
    name: str
    title: str
    required_metrics: list[str]

    # Each chart now owns its own fetch cadence/window instead of sharing one
    # global period+range for the whole page (see docs/UX_NOTES.md) — a
    # price-driven chart typically wants a daily "10y" window, an
    # income-statement chart wants ANNUAL/max, a margin ratio wants
    # QUARTERLY/max. `fetch_fundamentals`/`build_chart_specs` group charts by
    # this pair so charts that agree hit one fetch/cache entry, not one each.
    period: Period
    range: str

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
    """The *market's* currency symbol — right for `price` and anything derived from it (market
    cap), but not for a statement series, which can be filed in another currency (a TASE ticker
    quoted in ILS that files in USD). Use `currency_label` for those."""
    return "₪" if fundamentals.currency.value == "ILS" else "$"


def currency_label(fundamentals: CompanyFundamentals, *metric_ids: str) -> str:
    """Symbol for the currency the named series are actually denominated in (their `Money`
    tag), so an axis never claims the market's currency for statement data filed in another.

    One shared currency -> its symbol; the series disagree -> "mixed currencies" (they would
    be plotted on one axis in base units, so say so rather than pick one); no `Money` values
    at all (ratios, missing metric) -> the market's symbol, as before.
    """
    currencies = {
        p.value.currency
        for metric_id in metric_ids
        if (series := fundamentals.series.get(metric_id)) is not None
        for p in series.points
        if isinstance(p.value, Money)
    }
    if len(currencies) > 1:
        return "mixed currencies"
    if currencies:
        return "₪" if currencies.pop() == Currency.ILS else "$"
    return currency_symbol(fundamentals)


def render_money_bar(
    ax: Axes, fundamentals: CompanyFundamentals, metric_id: str
) -> None:
    """Shared bar-chart rendering for Money-valued metrics (revenue, net income, FCF, EPS)."""
    points = fundamentals.series[metric_id].points
    dates = [p.date for p in points]
    values = [p.value.value for p in points]

    ax.bar(dates, values, width=60, color="steelblue")
    ax.set_ylabel(
        f"{metric_id.replace('_', ' ').title()} ({currency_label(fundamentals, metric_id)})"
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
    ax.set_ylabel(
        f"({currency_label(fundamentals, *(metric_id for metric_id, _ in series))})"
    )
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
