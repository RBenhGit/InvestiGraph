import matplotlib

matplotlib.use("Agg")

from datetime import date
from unittest.mock import patch

import pytest

from investigraph.charts.catalog import get_chart
from investigraph.charts.registry import register_chart_set
from investigraph.sources.base import MissingCredentials, TickerNotFound
from investigraph.web.chart_set_store import ChartSetStore
from investigraph.template.models import (
    CompanyFundamentals,
    Currency,
    Market,
    MetricSeries,
    Money,
    Period,
    Point,
    Unit,
)
from investigraph.web.app import create_app


def _fundamentals() -> CompanyFundamentals:
    return CompanyFundamentals(
        ticker="AAPL",
        market=Market.US,
        currency=Currency.USD,
        period=Period.ANNUAL,
        range="10y",
        series={
            "price": MetricSeries(
                metric_id="price",
                points=[
                    Point(
                        date=date(2026, 1, 1),
                        value=Money(value=100, currency=Currency.USD, scale=Unit.ONES),
                    )
                ],
                available=True,
            )
        },
    )


def _fundamentals_by_period_range_for_charts(charts):
    """One fundamentals reused under every (period, range) key `charts`
    declare (see `charts/base.py`'s `Chart` protocol) — the stand-in for
    `web.service.load_fundamentals_for_charts` in tests that mock the fetch.
    """
    fundamentals = _fundamentals()
    return {(chart.period, chart.range): fundamentals for chart in charts}


def _patch_load_fundamentals_for_charts():
    """`patch()` context manager stubbing `load_fundamentals_for_charts` with
    one fundamentals per (period, range) key actually requested — a `charts`
    kwarg-agnostic replacement for the old single-`CompanyFundamentals`
    `load_fundamentals` mock these tests used before every chart owned its
    own period/range (see `charts/base.py`'s `Chart` protocol).
    """
    return patch(
        "investigraph.web.app.load_fundamentals_for_charts",
        side_effect=lambda ticker, source_name, charts: (
            _fundamentals_by_period_range_for_charts(charts)
        ),
    )


@pytest.fixture
def client(tmp_path):
    # tmp_path-backed store: create_app() now bootstrap-loads persisted chart
    # sets on startup, and this suite must not read or write the real
    # .cache/investigraph/chart_sets.json on whatever machine runs it.
    return create_app(chart_set_store=ChartSetStore(tmp_path)).test_client()


def test_index_shows_the_form(client):
    response = client.get("/")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'name="ticker"' in body
    assert "yfinance" in body
    assert "fundamentals" in body


def test_render_returns_dashboard_html(client):
    with _patch_load_fundamentals_for_charts():
        response = client.get("/render?ticker=AAPL&source=yfinance")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "AAPL" in body
    assert "<img" in body


def test_render_without_ticker_is_a_400(client):
    response = client.get("/render")
    assert response.status_code == 400
    assert "Enter a ticker" in response.get_data(as_text=True)


def test_render_unknown_ticker_shows_not_found(client):
    with patch(
        "investigraph.web.app.load_fundamentals_for_charts",
        side_effect=TickerNotFound("ZZZ"),
    ):
        response = client.get("/render?ticker=ZZZ")

    assert response.status_code == 404
    assert "not found" in response.get_data(as_text=True).lower()


def test_render_missing_credentials_names_env_var(client):
    with patch(
        "investigraph.web.app.get_source",
        side_effect=MissingCredentials("TWELVEDATA_API_KEY is not set"),
    ):
        response = client.get("/render?ticker=AAPL&source=twelvedata")

    assert response.status_code == 400
    assert "TWELVEDATA_API_KEY" in response.get_data(as_text=True)


def test_render_unknown_source_shows_error(client):
    response = client.get("/render?ticker=AAPL&source=not-a-real-source")

    assert response.status_code == 400
    assert "unknown data source" in response.get_data(as_text=True)


def test_index_lists_available_charts(client):
    response = client.get("/")

    body = response.get_data(as_text=True)
    assert 'name="charts"' in body
    assert 'value="fcf_margin"' in body


def test_index_annotates_charts_with_supporting_sources(client):
    response = client.get("/")

    body = response.get_data(as_text=True)
    assert "Supported by: twelvedata, yfinance" in body


def test_index_source_dropdown_reflects_the_live_registry(client):
    # The dropdown must be read live from sources/registry.py, not a
    # hand-maintained literal that can drift once a third source is
    # registered (the same failure shape as the fixed registry-dicts-drift
    # bug, recurring in this sibling module).
    with patch(
        "investigraph.web.app.registered_sources",
        return_value=["yfinance", "twelvedata", "acmedata"],
    ):
        response = client.get("/")

    body = response.get_data(as_text=True)
    assert 'value="acmedata"' in body


def test_index_chart_set_dropdown_reflects_the_live_registry(client):
    # Registered for real (not just a mocked registered_chart_sets return)
    # since index() now also resolves each name's own members via
    # get_chart_set() for the chart_set_members map — a name that only
    # exists in a mock would KeyError there.
    register_chart_set("growth", [get_chart("revenue")])

    response = client.get("/")

    body = response.get_data(as_text=True)
    assert 'value="growth"' in body


def test_render_with_charts_param_selects_only_named_charts(client):
    with _patch_load_fundamentals_for_charts():
        response = client.get("/render?ticker=AAPL&charts=price")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "<h3>Price</h3>" in body
    assert "<h3>Revenue</h3>" not in body


def test_render_with_unknown_chart_param_shows_error(client):
    response = client.get("/render?ticker=AAPL&charts=not-a-real-chart")

    assert response.status_code == 400
    assert "unknown chart" in response.get_data(as_text=True)


def test_render_with_duplicate_chart_params_renders_each_chart_once(client):
    with _patch_load_fundamentals_for_charts():
        response = client.get("/render?ticker=AAPL&charts=price&charts=price")

    assert response.status_code == 200
    assert response.get_data(as_text=True).count("<h3>Price</h3>") == 1


def test_render_with_empty_charts_param_falls_back_to_chart_set(client):
    with _patch_load_fundamentals_for_charts():
        response = client.get("/render?ticker=AAPL&charts=")

    assert response.status_code == 200


def test_render_normalizes_lowercase_ticker(client, monkeypatch):
    # The source comes from config.data_source_name(), i.e. the environment: clear it so
    # this asserts the code default rather than whatever the developer's local env sets.
    monkeypatch.delenv("DATA_SOURCE", raising=False)
    with _patch_load_fundamentals_for_charts() as mock_load:
        response = client.get("/render?ticker=aapl&charts=price")

    assert response.status_code == 200
    # "price" is the only requested chart, so the grouped fetch should be
    # called with exactly that one chart, under the normalized ticker.
    mock_load.assert_called_once()
    called_ticker, called_source, called_charts = mock_load.call_args[0]
    assert called_ticker == "AAPL"
    assert called_source == "twelvedata"
    assert [c.name for c in called_charts] == ["price"]


def test_render_rejects_invalid_ticker(client):
    response = client.get("/render?ticker=../../etc/passwd")

    assert response.status_code == 400
    assert "Invalid ticker" in response.get_data(as_text=True)


def test_render_rejects_unknown_chart_set(client):
    response = client.get("/render?ticker=AAPL&chart_set=not-a-real-set")

    assert response.status_code == 400
    assert "unknown chart set" in response.get_data(as_text=True).lower()


def test_render_rejects_a_chart_whose_own_period_the_source_does_not_declare(client):
    # Each chart now owns its own period (see charts/base.py's Chart
    # protocol) instead of one global period picked in the top menu — this
    # exercises that the pre-fetch capability gate still runs, now per the
    # requested chart's own declared period rather than a request-wide one.
    # "margins" declares Period.QUARTERLY; a source declaring only ANNUAL
    # must still be rejected before any fetch is attempted.
    from investigraph.sources.base import Capability
    from investigraph.template.models import Market

    stub_capability = Capability(
        markets={Market.US, Market.TASE},
        periods={Period.ANNUAL},
        max_history={Period.ANNUAL: 5},
        metrics={"gross_margin", "net_margin"},
    )

    class _AnnualOnlyAdapter:
        def capability(self) -> Capability:
            return stub_capability

    with patch("investigraph.web.app.get_source", return_value=_AnnualOnlyAdapter()):
        response = client.get("/render?ticker=AAPL&charts=margins")

    assert response.status_code == 400
    assert "does not support period quarterly" in response.get_data(as_text=True)


def test_chart_data_returns_dashboard_json(client):
    with _patch_load_fundamentals_for_charts():
        response = client.get("/chart-data?ticker=AAPL&source=yfinance&charts=price")

    assert response.status_code == 200
    body = response.get_json()
    assert body["ticker"] == "AAPL"
    assert body["market"] == "US"
    assert body["currency"] == "USD"
    assert [c["name"] for c in body["charts"]] == ["price"]
    assert body["charts"][0]["kind"] == "line"


def test_chart_data_without_ticker_is_a_400(client):
    response = client.get("/chart-data")

    assert response.status_code == 400
    assert "Enter a ticker" in response.get_json()["error"]


def test_chart_data_unknown_ticker_shows_not_found(client):
    with patch(
        "investigraph.web.app.load_fundamentals_for_charts",
        side_effect=TickerNotFound("ZZZ"),
    ):
        response = client.get("/chart-data?ticker=ZZZ")

    assert response.status_code == 404
    assert "not found" in response.get_json()["error"].lower()


def test_chart_data_missing_credentials_names_env_var(client):
    with patch(
        "investigraph.web.app.get_source",
        side_effect=MissingCredentials("TWELVEDATA_API_KEY is not set"),
    ):
        response = client.get("/chart-data?ticker=AAPL&source=twelvedata")

    assert response.status_code == 400
    assert "TWELVEDATA_API_KEY" in response.get_json()["error"]


def test_chart_data_rejects_unknown_chart_set(client):
    response = client.get("/chart-data?ticker=AAPL&chart_set=not-a-real-set")

    assert response.status_code == 400
    assert "unknown chart set" in response.get_json()["error"].lower()


def test_chart_data_with_unknown_chart_param_shows_error(client):
    response = client.get("/chart-data?ticker=AAPL&charts=not-a-real-chart")

    assert response.status_code == 400
    assert "unknown chart" in response.get_json()["error"]


@pytest.mark.parametrize("route", ["/render", "/chart-data"])
def test_data_source_env_var_is_honored_when_no_source_param_is_given(
    client, monkeypatch, route
):
    monkeypatch.setenv("DATA_SOURCE", "yfinance")
    with _patch_load_fundamentals_for_charts() as mock_load:
        response = client.get(f"{route}?ticker=AAPL&charts=price")

    assert response.status_code == 200
    assert mock_load.call_args[0][1] == "yfinance"


def test_chart_data_normalizes_lowercase_ticker(client, monkeypatch):
    monkeypatch.delenv("DATA_SOURCE", raising=False)
    with _patch_load_fundamentals_for_charts() as mock_load:
        response = client.get("/chart-data?ticker=aapl&charts=price")

    assert response.status_code == 200
    mock_load.assert_called_once()
    called_ticker, called_source, called_charts = mock_load.call_args[0]
    assert called_ticker == "AAPL"
    assert called_source == "twelvedata"
    assert [c.name for c in called_charts] == ["price"]


def test_create_chart_set_succeeds_and_shows_up_in_the_dropdown(client):
    # Names prefixed "picker_" throughout this file are unique to these tests —
    # _CHART_SETS is process-global and never evicted, so a name shared with
    # another test (e.g. "growth", used by
    # test_index_chart_set_dropdown_reflects_the_live_registry) would collide.
    response = client.post(
        "/chart-sets", data={"name": "picker_alpha", "charts": ["revenue", "eps"]}
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body == {"ok": True, "name": "picker_alpha", "charts": ["revenue", "eps"]}

    index_body = client.get("/").get_data(as_text=True)
    assert 'value="picker_alpha"' in index_body


def test_create_chart_set_requires_a_name(client):
    response = client.post("/chart-sets", data={"charts": ["revenue"]})

    assert response.status_code == 400
    assert "name" in response.get_json()["error"].lower()


def test_create_chart_set_rejects_a_duplicate_name(client):
    response = client.post(
        "/chart-sets", data={"name": "fundamentals", "charts": ["revenue"]}
    )

    assert response.status_code == 400
    assert "already exists" in response.get_json()["error"]


def test_create_chart_set_requires_at_least_one_chart(client):
    response = client.post("/chart-sets", data={"name": "picker_beta"})

    assert response.status_code == 400
    assert "select at least one" in response.get_json()["error"].lower()


def test_create_chart_set_rejects_an_unknown_chart(client):
    response = client.post(
        "/chart-sets", data={"name": "picker_gamma", "charts": ["not-a-real-chart"]}
    )

    assert response.status_code == 400
    assert "unknown chart" in response.get_json()["error"]


def test_create_chart_set_rejects_the_reserved_custom_prefix(client):
    response = client.post(
        "/chart-sets", data={"name": "custom:picker_delta", "charts": ["revenue"]}
    )

    assert response.status_code == 400
    assert "custom:" in response.get_json()["error"]


def test_created_chart_set_persists_across_a_server_restart(tmp_path):
    store = ChartSetStore(tmp_path)
    first_run = create_app(chart_set_store=store).test_client()
    first_run.post(
        "/chart-sets", data={"name": "picker_epsilon", "charts": ["revenue", "eps"]}
    )

    # A fresh create_app() call against the same on-disk store simulates
    # restarting `python -m investigraph.web` — the bootstrap loop in
    # create_app() should re-register what was saved above.
    second_run = create_app(chart_set_store=store).test_client()
    index_body = second_run.get("/").get_data(as_text=True)

    assert 'value="picker_epsilon"' in index_body


def test_bootstrap_skips_a_persisted_set_with_a_since_removed_chart_id(tmp_path):
    store = ChartSetStore(tmp_path)
    store.save("picker_zeta", ["not-a-real-chart"])

    # Must not crash create_app() — a chart id that no longer resolves (e.g.
    # removed from the catalog since the set was saved) is a declared gap,
    # not a startup failure.
    index_body = (
        create_app(chart_set_store=store).test_client().get("/").get_data(as_text=True)
    )

    assert 'value="picker_zeta"' not in index_body
