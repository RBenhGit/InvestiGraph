"""Chart <-> source compatibility, kept out of both `charts/` and `sources/` so
neither package has to import the other — `charts/` stays display-only and
`sources/` stays data-only, matching the one-way pipeline in CLAUDE.md.
"""

from financial_charts.charts.base import Chart
from financial_charts.charts.catalog import available_charts
from financial_charts.sources.base import Capability
from financial_charts.sources.registry import get_capability, registered_sources


def supported_by(chart: Chart) -> frozenset[str]:
    """Registered source names whose declared `Capability` supplies every metric
    `chart` requires.

    Reads only the static `capability.py` declarations (offline, no adapter
    instantiated) — lets a chart developer see, at design time, which sources
    can actually render a chart before shipping it.
    """
    return frozenset(
        name
        for name in registered_sources()
        if set(chart.required_metrics) <= get_capability(name).metrics
    )


def chart_support() -> dict[str, frozenset[str]]:
    """Chart id -> the sources that can supply it, for every catalog chart."""
    return {chart.name: supported_by(chart) for chart in available_charts()}


def capability_limits(charts: list[Chart], capability: Capability) -> list[str]:
    """Advisory limits for charts whose required metrics aren't declared by
    `capability` — the same "surface it, don't block it" pattern as
    `validation.check_request`. A chart missing its metrics already degrades
    gracefully to a "No Data" card; this just explains why upfront instead of
    leaving the user to guess.
    """
    limits = []
    for chart in charts:
        missing = sorted(set(chart.required_metrics) - capability.metrics)
        if missing:
            limits.append(f"{chart.name}: source does not declare {', '.join(missing)}")
    return limits
