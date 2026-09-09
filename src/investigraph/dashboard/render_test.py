import matplotlib

matplotlib.use("Agg")

import pytest

from investigraph.charts.builtins._test_helpers import (
    fundamentals_with,
    money_series,
)
from investigraph.charts.registry import get_chart_set
from investigraph.dashboard.render import render_html, write_output


def _fundamentals():
    fundamentals = fundamentals_with({"price": money_series("price", [1.0, 2.0, 3.0])})
    fundamentals.source_limits.append("eps: no data available for this ticker")
    return fundamentals


def _fundamentals_by_period_range(chart_set_name: str = "fundamentals"):
    """One hand-built fundamentals reused under every (period, range) key the
    named chart set's charts declare (see `charts/base.py`'s `Chart`
    protocol) — these tests exercise page/output assembly, not per-chart
    fetch plumbing.
    """
    fundamentals = _fundamentals()
    return {
        (chart.period, chart.range): fundamentals
        for chart in get_chart_set(chart_set_name)
    }


def test_render_html_includes_ticker_and_currency():
    html = render_html(_fundamentals_by_period_range(), "fundamentals")

    assert "TEST" in html
    assert "USD" in html
    assert "<img" in html


def test_render_html_lists_source_limits():
    html = render_html(_fundamentals_by_period_range(), "fundamentals")

    assert "eps: no data available for this ticker" in html


def test_write_output_html(tmp_path):
    out = tmp_path / "out.html"
    write_output(_fundamentals_by_period_range(), out, "fundamentals")

    assert out.exists()
    assert "TEST" in out.read_text()


def test_write_output_png(tmp_path):
    out = tmp_path / "out.png"
    write_output(_fundamentals_by_period_range(), out, "fundamentals")

    assert out.exists()
    assert out.stat().st_size > 0


def test_write_output_rejects_unsupported_suffix(tmp_path):
    out = tmp_path / "out.svg"
    with pytest.raises(ValueError, match="unsupported output format"):
        write_output(_fundamentals_by_period_range(), out, "fundamentals")
