from financial_charts.chart_support import (
    capability_limits,
    chart_support,
    supported_by,
)
from financial_charts.charts.catalog import available_charts
from financial_charts.sources.base import Capability
from financial_charts.template.models import Market, Period


class _StubChart:
    name = "stub"
    title = "Stub"
    required_metrics = ["goodwill_impairment"]

    def render(self, ax, fundamentals):
        pass


class _PriceOnlyChart:
    name = "price-only"
    title = "Price Only"
    required_metrics = ["price"]

    def render(self, ax, fundamentals):
        pass


def test_supported_by_is_empty_when_no_source_declares_the_metric():
    assert supported_by(_StubChart()) == frozenset()


def test_supported_by_lists_sources_that_declare_all_required_metrics():
    assert supported_by(_PriceOnlyChart()) == {"yfinance", "twelvedata"}


def test_chart_support_covers_every_catalog_chart():
    support = chart_support()

    assert set(support) == {chart.name for chart in available_charts()}
    assert support["fcf_margin"] == {"yfinance", "twelvedata"}


def _capability(**overrides) -> Capability:
    defaults = dict(
        markets={Market.US},
        periods={Period.ANNUAL},
        max_history={Period.ANNUAL: 4},
        metrics={"price"},
    )
    defaults.update(overrides)
    return Capability(**defaults)


def test_capability_limits_is_empty_when_every_chart_is_supported():
    cap = _capability(metrics={"price"})
    assert capability_limits([_PriceOnlyChart()], cap) == []


def test_capability_limits_flags_charts_with_missing_metrics():
    cap = _capability(metrics=set())
    limits = capability_limits([_StubChart()], cap)

    assert len(limits) == 1
    assert "stub" in limits[0]
    assert "goodwill_impairment" in limits[0]
