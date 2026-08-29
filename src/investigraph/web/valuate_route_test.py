"""Contract tests for POST /api/valuate, ported from Eps_Evaluation's
server.test.ts (legacy/eps_evaluation/src/web/server.test.ts) onto this Flask
route. Mocks load_fundamentals/fetch_analyst_consensus at their
investigraph.web.valuate_service import location, matching server.test.ts's
own vi.mock('../data/twelvedata')/vi.mock('../data/yahoo') boundary.
"""

from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest

from investigraph.sources.base import TickerNotFound
from investigraph.sources.yahoo_consensus.models import (
    AnalystConsensus,
    AnalystPriceTarget,
)
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
from investigraph.web.chart_set_store import ChartSetStore

TICKER = "AAPL"


def _money(value: float) -> Money:
    return Money(value=value, currency=Currency.USD, scale=Unit.ONES)


def _fundamentals(
    *,
    eps_values: list[float] | None = None,
    current_price: float = 200,
) -> CompanyFundamentals:
    eps_values = eps_values if eps_values is not None else [6, 6.5, 7, 8, 9, 10]
    eps_dates = [date(2020 + i, 12, 31) for i in range(len(eps_values))]
    return CompanyFundamentals(
        ticker=TICKER,
        market=Market.US,
        currency=Currency.USD,
        period=Period.ANNUAL,
        range="5y",
        series={
            "eps": MetricSeries(
                metric_id="eps",
                points=[
                    Point(date=d, value=_money(v))
                    for d, v in zip(eps_dates, eps_values)
                ],
                available=True,
            ),
            "price": MetricSeries(
                metric_id="price",
                points=[Point(date=date(2026, 8, 1), value=_money(current_price))],
                available=True,
            ),
        },
    )


def _consensus(**overrides) -> AnalystConsensus:
    fields = dict(
        ticker=TICKER,
        price_target=AnalystPriceTarget(),
        as_of=datetime.now(timezone.utc),
    )
    fields.update(overrides)
    return AnalystConsensus(**fields)


@pytest.fixture
def client(tmp_path):
    return create_app(chart_set_store=ChartSetStore(tmp_path)).test_client()


def _patched(fundamentals=None, fundamentals_error=None, consensus=None):
    load_target = patch("investigraph.web.valuate_service.load_fundamentals")
    consensus_target = patch("investigraph.web.valuate_service.fetch_analyst_consensus")
    load_mock = load_target.start()
    consensus_mock = consensus_target.start()
    if fundamentals_error is not None:
        load_mock.side_effect = fundamentals_error
    else:
        load_mock.return_value = (
            fundamentals if fundamentals is not None else _fundamentals()
        )
    consensus_mock.return_value = consensus
    return load_target, consensus_target


def _stop(patches):
    for p in patches:
        p.stop()


def test_returns_200_with_fair_values_matching_direct_calls(client):
    patches = _patched(consensus=_consensus())
    try:
        response = client.post(
            "/api/valuate",
            json={
                "ticker": TICKER,
                "growthRatePercent": 10,
                "exitPeMultiple": 15,
                "requiredReturnPercent": 15,
                "years": 10,
            },
        )
        assert response.status_code == 200
        body = response.get_json()
        assert body["ok"] is True
        assert body["ruleOne"]["base"]["ok"] is True
        assert body["analystConsensus"] is not None
    finally:
        _stop(patches)


def test_passes_mos_percent_to_rule_one(client):
    patches = _patched()
    try:
        response = client.post(
            "/api/valuate",
            json={
                "ticker": TICKER,
                "growthRatePercent": 10,
                "exitPeMultiple": 15,
                "requiredReturnPercent": 10,
                "years": 10,
                "mosPercent": 25,
            },
        )
        body = response.get_json()
        assert body["ruleOne"]["base"]["inputs"]["mosPercent"] == 25
        # g == r collapses to eps * exitPe = 150; 25% MoS -> 112.5
        assert body["ruleOne"]["base"]["fairValue"] == pytest.approx(112.5)
    finally:
        _stop(patches)


def test_uses_user_provided_bear_bull_values_not_hardcoded_defaults(client):
    patches = _patched()
    try:
        response = client.post(
            "/api/valuate",
            json={
                "ticker": TICKER,
                "growthRatePercent": 10,
                "exitPeMultiple": 15,
                "requiredReturnPercent": 15,
                "years": 10,
                "bearGrowthRatePercent": -2,
                "bearExitPeMultiple": 8,
                "bearRequiredReturnPercent": 20,
                "bullGrowthRatePercent": 30,
                "bullExitPeMultiple": 25,
                "bullRequiredReturnPercent": 10,
            },
        )
        body = response.get_json()
        assert body["bearGrowth"] == -2
        assert body["bullGrowth"] == 30
        assert body["ruleOne"]["bear"]["inputs"]["exitPeMultiple"] == 8
        assert body["ruleOne"]["bull"]["inputs"]["exitPeMultiple"] == 25
    finally:
        _stop(patches)


def test_derives_bear_bull_growth_from_base_when_omitted(client):
    patches = _patched()
    try:
        response = client.post(
            "/api/valuate",
            json={
                "ticker": TICKER,
                "growthRatePercent": 10,
                "exitPeMultiple": 15,
                "requiredReturnPercent": 15,
                "years": 10,
            },
        )
        body = response.get_json()
        assert body["bearGrowth"] == pytest.approx(7.5)  # 10 * 0.75
        assert body["bullGrowth"] == pytest.approx(12.5)  # 10 * 1.25
    finally:
        _stop(patches)


def test_surfaces_a_non_2xx_response_when_fundamentals_fetch_fails(client):
    patches = _patched(fundamentals_error=TickerNotFound(TICKER))
    try:
        response = client.post(
            "/api/valuate",
            json={
                "ticker": TICKER,
                "exitPeMultiple": 15,
                "requiredReturnPercent": 15,
                "years": 10,
            },
        )
        assert response.status_code == 404
        body = response.get_json()
        assert body["ok"] is False
        assert body["error"]["type"] == "NOT_FOUND"
    finally:
        _stop(patches)


def test_still_returns_200_with_analyst_consensus_null_when_yahoo_lookup_fails(client):
    patches = _patched(consensus=None)
    try:
        response = client.post(
            "/api/valuate",
            json={
                "ticker": TICKER,
                "growthRatePercent": 10,
                "exitPeMultiple": 15,
                "requiredReturnPercent": 15,
                "years": 10,
            },
        )
        assert response.status_code == 200
        body = response.get_json()
        assert body["ok"] is True
        assert body["analystConsensus"] is None
    finally:
        _stop(patches)


def test_eps_source_twelvedata_when_no_stale_warning(client):
    # No Yahoo trailing_eps to compare against -> no divergence -> "twelvedata".
    patches = _patched(consensus=_consensus(trailing_eps=None))
    try:
        response = client.post(
            "/api/valuate",
            json={
                "ticker": TICKER,
                "growthRatePercent": 10,
                "exitPeMultiple": 15,
                "requiredReturnPercent": 15,
                "years": 10,
            },
        )
        body = response.get_json()
        assert body["effectiveEps"] == 10  # latest annual eps point
        assert body["epsSource"] == "twelvedata"
    finally:
        _stop(patches)


def test_eps_source_yahoo_fallback_on_large_divergence(client):
    # Template eps_ttm=10 vs Yahoo trailing_eps=7 -> ~42% divergence -> stale, Yahoo usable.
    patches = _patched(consensus=_consensus(trailing_eps=7.0))
    try:
        response = client.post(
            "/api/valuate",
            json={
                "ticker": TICKER,
                "growthRatePercent": 10,
                "exitPeMultiple": 15,
                "requiredReturnPercent": 15,
                "years": 10,
            },
        )
        body = response.get_json()
        assert body["effectiveEps"] == 7.0
        assert body["epsSource"] == "yahoo-fallback"
        assert "Yahoo" in body["epsSourceDetail"]
    finally:
        _stop(patches)


def test_eps_source_stale_no_fallback_when_yahoo_figure_not_positive(client):
    patches = _patched(consensus=_consensus(trailing_eps=-3.0))
    try:
        response = client.post(
            "/api/valuate",
            json={
                "ticker": TICKER,
                "growthRatePercent": 10,
                "exitPeMultiple": 15,
                "requiredReturnPercent": 15,
                "years": 10,
            },
        )
        body = response.get_json()
        assert body["effectiveEps"] == 10
        assert body["epsSource"] == "twelvedata-stale-no-fallback"
    finally:
        _stop(patches)


def test_eps_override_wins_with_null_eps_source(client):
    patches = _patched(consensus=_consensus(trailing_eps=7.0))
    try:
        response = client.post(
            "/api/valuate",
            json={
                "ticker": TICKER,
                "epsOverride": 5,
                "growthRatePercent": 10,
                "exitPeMultiple": 15,
                "requiredReturnPercent": 15,
                "years": 10,
            },
        )
        body = response.get_json()
        assert body["effectiveEps"] == 5
        assert body["epsSource"] is None
    finally:
        _stop(patches)


def test_seeds_growth_from_historical3y_uncapped_when_growth_omitted(client):
    # eps ascending by date [2020..2025] = [2,3,4,5,7,10]; historical_3y compares the
    # latest (2025=10) against the one 3 years back (2022=4): CAGR=(10/4)^(1/3)-1
    # ~= 35.7%, comfortably above the old undocumented 15% web-only cap this proves
    # is gone (the CLI's fallback chain -- analystEstimate5y -> historical3y ->
    # historical1y -- was never capped; this merge uses that exact chain for both
    # entry points).
    fundamentals = _fundamentals(eps_values=[2, 3, 4, 5, 7, 10])
    patches = _patched(fundamentals=fundamentals, consensus=_consensus())
    try:
        response = client.post(
            "/api/valuate",
            json={
                "ticker": TICKER,
                "exitPeMultiple": 15,
                "requiredReturnPercent": 15,
                "years": 10,
            },
        )
        body = response.get_json()
        assert body["ok"] is True
        assert body["effectiveGrowth"] == pytest.approx((10 / 4) ** (1 / 3) * 100 - 100)
    finally:
        _stop(patches)


def test_returns_missing_growth_rate_not_a_fabricated_zero(client):
    # Single eps point: no historical_1y/_3y possible, no analyst source in this merge.
    patches = _patched(
        fundamentals=_fundamentals(eps_values=[10]), consensus=_consensus()
    )
    try:
        response = client.post(
            "/api/valuate",
            json={
                "ticker": TICKER,
                "exitPeMultiple": 15,
                "requiredReturnPercent": 15,
                "years": 10,
            },
        )
        assert response.status_code == 200
        body = response.get_json()
        assert body["ok"] is True
        assert body["effectiveGrowth"] is None
        missing = {"ok": False, "error": "MISSING_GROWTH_RATE"}
        assert body["ruleOne"] == {"base": missing, "bear": missing, "bull": missing}
    finally:
        _stop(patches)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"ticker": None},
        {"ticker": 12345},
        {"ticker": {"evil": True}},
        {"ticker": "   "},
    ],
)
def test_returns_typed_400_not_unhandled_500_for_malformed_ticker(client, payload):
    load_target = patch("investigraph.web.valuate_service.load_fundamentals")
    load_mock = load_target.start()
    try:
        response = client.post(
            "/api/valuate",
            json={
                "exitPeMultiple": 15,
                "requiredReturnPercent": 15,
                "years": 10,
                **payload,
            },
        )
        assert response.status_code == 400
        body = response.get_json()
        assert body["ok"] is False
        assert body["error"]["type"] == "INSUFFICIENT_DATA"
        assert "ticker" in body["error"]["reason"].lower()
        load_mock.assert_not_called()
    finally:
        load_target.stop()


def test_rejects_a_ticker_the_cache_layer_cannot_safely_use_in_a_filename(client):
    load_target = patch("investigraph.web.valuate_service.load_fundamentals")
    load_mock = load_target.start()
    try:
        response = client.post(
            "/api/valuate",
            json={
                "ticker": "AAPL/../ETC",
                "exitPeMultiple": 15,
                "requiredReturnPercent": 15,
                "years": 10,
            },
        )
        assert response.status_code == 400
        body = response.get_json()
        assert body["error"]["type"] == "INSUFFICIENT_DATA"
        load_mock.assert_not_called()
    finally:
        load_target.stop()


def test_returns_typed_400_for_a_missing_request_body(client):
    response = client.post("/api/valuate", content_type="application/json", data="")
    assert response.status_code == 400
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"]["type"] == "INSUFFICIENT_DATA"


def test_returns_typed_400_for_a_literal_null_body(client):
    response = client.post("/api/valuate", json=None)
    assert response.status_code == 400
    body = response.get_json()
    assert body["ok"] is False


def test_echoes_actual_bear_growth_even_when_the_scenario_fails(
    client,
):
    patches = _patched(consensus=_consensus())
    try:
        response = client.post(
            "/api/valuate",
            json={
                "ticker": TICKER,
                "growthRatePercent": 10,
                "exitPeMultiple": 15,
                "bearExitPeMultiple": 0,  # trips ruleOne's INVALID_EXIT_PE
                "bearGrowthRatePercent": -5,
                "requiredReturnPercent": 15,
                "years": 10,
            },
        )
        body = response.get_json()
        assert body["ok"] is True
        assert body["ruleOne"]["bear"]["ok"] is False
        assert body["ruleOne"]["bear"]["error"] == "INVALID_EXIT_PE"
        assert body["bearGrowth"] == -5
    finally:
        _stop(patches)
