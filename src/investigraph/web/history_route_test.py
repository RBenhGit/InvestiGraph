"""Contract tests for the history/valuations routes, ported from
Eps_Evaluation's server.test.ts (legacy/eps_evaluation/src/web/server.test.ts).

Unlike valuate_route_test.py, these don't mock the underlying store --
history/store.py already has its own thorough persistence test suite
(history/store_test.py); these tests exercise the real store against a
tmp_path-backed HISTORY_FILE_PATH, focused on the route layer's own job:
status codes, the camelCase<->snake_case boundary, and error mapping.
"""

import pytest

from investigraph.web.app import create_app
from investigraph.web.chart_set_store import ChartSetStore


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HISTORY_FILE_PATH", str(tmp_path / "history-test.json"))
    return create_app(chart_set_store=ChartSetStore(tmp_path)).test_client()


def _payload(**overrides):
    fields = dict(
        ticker="AAPL",
        currentPrice=220,
        currency="USD",
        epsTtm=6.5,
        growthRatePercent=12,
        exitPeMultiple=25,
        requiredReturnPercent=15,
        years=5,
        ruleOneFairValue=180,
    )
    fields.update(overrides)
    return fields


def test_post_then_get_round_trips_camelcase_fields(client):
    post_response = client.post("/api/history", json=_payload())
    assert post_response.status_code == 201
    saved = post_response.get_json()
    assert saved["ok"] is True
    assert saved["data"]["ticker"] == "AAPL"
    assert saved["data"]["growthRatePercent"] == 12
    assert saved["data"]["ruleOneFairValue"] == 180
    assert saved["data"]["id"]  # auto-generated
    assert saved["data"]["evaluatedAt"]  # auto-generated

    get_response = client.get("/api/history?ticker=AAPL")
    assert get_response.status_code == 200
    body = get_response.get_json()
    assert body["ok"] is True
    assert len(body["data"]) == 1
    assert body["data"][0]["id"] == saved["data"]["id"]


def test_post_with_blank_ticker_returns_400_invalid_input(client):
    response = client.post("/api/history", json=_payload(ticker="   "))
    assert response.status_code == 400
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"]["type"] == "INVALID_INPUT"


def test_post_with_wrong_typed_field_returns_400_not_a_500(client):
    # currentPrice must be a number -- a string should be a typed 400, not an
    # unhandled 500 leaking a Pydantic traceback.
    response = client.post("/api/history", json=_payload(currentPrice="not a number"))
    assert response.status_code == 400
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"]["type"] == "INVALID_INPUT"


def test_post_with_nested_scenario_fields_round_trips(client):
    payload = _payload(
        base={
            "growthRatePercent": 10,
            "exitPeMultiple": 15,
            "requiredReturnPercent": 15,
            "mosPercent": 0,
            "ruleOneFairValue": 110,
        }
    )
    response = client.post("/api/history", json=payload)
    assert response.status_code == 201
    saved = response.get_json()["data"]
    assert saved["base"]["growthRatePercent"] == 10
    assert saved["base"]["ruleOneFairValue"] == 110


def test_delete_removes_a_saved_valuation(client):
    saved = client.post("/api/history", json=_payload()).get_json()["data"]

    response = client.delete(f"/api/history/{saved['id']}")
    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["data"]["id"] == saved["id"]

    remaining = client.get("/api/history").get_json()
    assert remaining["data"] == []


def test_delete_returns_404_when_not_found(client):
    response = client.delete("/api/history/does-not-exist")
    assert response.status_code == 404
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"]["type"] == "NOT_FOUND"


def test_get_history_returns_empty_list_when_no_file_exists(client):
    response = client.get("/api/history")
    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["data"] == []


def test_valuations_route_returns_latest_per_ticker_per_evaluator(client):
    client.post("/api/history", json=_payload(ticker="AAPL", evaluator="Ran"))
    client.post("/api/history", json=_payload(ticker="MSFT", evaluator="Ran"))
    client.post("/api/history", json=_payload(ticker="AAPL", evaluator="Aviv"))

    response = client.get("/api/valuations")
    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    tickers_and_evaluators = {(r["ticker"], r["evaluator"]) for r in body["data"]}
    assert tickers_and_evaluators == {
        ("AAPL", "Ran"),
        ("MSFT", "Ran"),
        ("AAPL", "Aviv"),
    }
