"""Contract tests for GET /api/live-prices, ported from Eps_Evaluation's
server.ts handler (not covered by server.test.ts -- no original test exists
to port; these were written directly against the route's own behavior)."""

from unittest.mock import MagicMock, patch

import pytest

from investigraph.web.app import create_app
from investigraph.web.chart_set_store import ChartSetStore


@pytest.fixture
def client(tmp_path):
    return create_app(chart_set_store=ChartSetStore(tmp_path)).test_client()


def _mock_ticker(last_price):
    ticker = MagicMock()
    ticker.fast_info = {"lastPrice": last_price} if last_price is not None else {}
    return ticker


def test_returns_400_when_tickers_param_is_missing(client):
    response = client.get("/api/live-prices")
    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_returns_400_when_tickers_param_is_only_commas(client):
    response = client.get("/api/live-prices?tickers=,,,")
    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_returns_prices_keyed_by_uppercased_ticker(client):
    with patch("investigraph.web.app.yf.Ticker") as mock_ticker_cls:
        mock_ticker_cls.side_effect = lambda t: _mock_ticker(
            {"aapl": 220.5, "msft": 410.0}[t.lower()]
        )
        response = client.get("/api/live-prices?tickers=aapl, MSFT ")

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["prices"] == {"AAPL": 220.5, "MSFT": 410.0}


def test_one_bad_ticker_does_not_fail_the_whole_batch(client):
    def side_effect(ticker):
        if ticker == "BADTICKER":
            raise Exception("no data found")
        return _mock_ticker(220.5)

    with patch("investigraph.web.app.yf.Ticker") as mock_ticker_cls:
        mock_ticker_cls.side_effect = side_effect
        response = client.get("/api/live-prices?tickers=AAPL,BADTICKER")

    assert response.status_code == 200
    body = response.get_json()
    assert body["prices"] == {"AAPL": 220.5}


def test_a_ticker_with_no_last_price_is_omitted_not_a_failure(client):
    with patch("investigraph.web.app.yf.Ticker") as mock_ticker_cls:
        mock_ticker_cls.return_value = _mock_ticker(None)
        response = client.get("/api/live-prices?tickers=DELISTED")

    assert response.status_code == 200
    body = response.get_json()
    assert body["prices"] == {}
