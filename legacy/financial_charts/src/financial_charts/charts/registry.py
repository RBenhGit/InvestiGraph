from financial_charts.charts.base import Chart
from financial_charts.charts.catalog import get_chart

# Shared with __main__.py/web/app.py, which each build an ad-hoc set name as
# CUSTOM_CHART_SET_PREFIX + ",".join(sorted(chart_ids)) for one-off
# --charts/checkbox selections — a single published constant so the producers
# and registered_chart_sets()'s exclusion filter below can't drift apart.
CUSTOM_CHART_SET_PREFIX = "custom:"

_CHART_SETS: dict[str, list[Chart]] = {
    # `fcf_margin` is deliberately not in the default grid — it's still
    # available via --charts/the web checkbox picker, just not curated into
    # the default 6-chart page. Kept a deliberate choice by
    # registry_test.py::test_builtin_fundamentals_set_has_six_charts pinning
    # the exact set, so a new catalog chart can't silently join the default.
    "fundamentals": [
        get_chart("price"),
        get_chart("revenue"),
        get_chart("net_income"),
        get_chart("free_cash_flow"),
        get_chart("eps"),
        get_chart("margins"),
    ]
}


def register_chart_set(name: str, charts: list[Chart]) -> None:
    """Register a custom named chart set for the dashboard to render."""
    _CHART_SETS[name] = charts


def get_chart_set(name: str) -> list[Chart]:
    try:
        return _CHART_SETS[name]
    except KeyError:
        raise KeyError(
            f"unknown chart set {name!r}; registered sets: {sorted(_CHART_SETS)}"
        ) from None


def registered_chart_sets() -> list[str]:
    """Curated, named chart sets meant for a picker (e.g. the web dropdown).

    Excludes the ad-hoc `CUSTOM_CHART_SET_PREFIX`-named sets that
    `__main__.py`/`web/app.py` register on the fly for one-off
    `--charts`/checkbox selections — those are a different mechanism, not a
    curated option a user should choose from a list.
    """
    return sorted(
        name for name in _CHART_SETS if not name.startswith(CUSTOM_CHART_SET_PREFIX)
    )
