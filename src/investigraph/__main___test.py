from datetime import date
from unittest.mock import patch

import pytest

from investigraph.__main__ import main
from investigraph.sources.base import Capability, MissingCredentials, TickerNotFound
from investigraph.sources.commission import CommissionCertificate, SampleResult
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


def _fundamentals(ticker: str = "AAPL") -> CompanyFundamentals:
    return CompanyFundamentals(
        ticker=ticker,
        market=Market.US,
        currency=Currency.USD,
        period=Period.ANNUAL,
        range="5y",
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


def _capability() -> Capability:
    return Capability(
        markets={Market.US, Market.TASE},
        periods={Period.ANNUAL},
        max_history={Period.ANNUAL: 5},
        metrics={"price"},
    )


class _StubAdapter:
    def __init__(self, fundamentals=None, fetch_error=None):
        self._fundamentals = fundamentals or _fundamentals()
        self._fetch_error = fetch_error

    def capability(self) -> Capability:
        return _capability()

    def fetch(self, ticker, market, period, range) -> CompanyFundamentals:
        if self._fetch_error:
            raise self._fetch_error
        return self._fundamentals


def test_render_writes_html_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "out.html"

    with patch("investigraph.__main__.get_source", return_value=_StubAdapter()):
        code = main(["AAPL", "--out", str(out)])

    assert code == 0
    assert out.exists()
    assert "AAPL" in out.read_text()


def test_render_unknown_ticker_returns_error(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    with patch(
        "investigraph.__main__.get_source",
        return_value=_StubAdapter(fetch_error=TickerNotFound("ZZZ")),
    ):
        code = main(["ZZZ", "--out", str(tmp_path / "out.html")])

    assert code == 1
    assert "not found" in capsys.readouterr().err


def test_render_missing_credentials_returns_error(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    with patch(
        "investigraph.__main__.get_source",
        side_effect=MissingCredentials("TWELVEDATA_API_KEY is not set"),
    ):
        code = main(
            ["AAPL", "--source", "twelvedata", "--out", str(tmp_path / "out.html")]
        )

    assert code == 1
    assert "TWELVEDATA_API_KEY" in capsys.readouterr().err


def test_render_unknown_source_returns_error(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    code = main(
        ["AAPL", "--source", "not-a-real-source", "--out", str(tmp_path / "out.html")]
    )

    assert code == 1
    assert "unknown data source" in capsys.readouterr().err


def test_render_uses_cache_before_fetching(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fetch_calls = []

    class _CountingAdapter(_StubAdapter):
        def fetch(self, ticker, market, period, range):
            fetch_calls.append(ticker)
            return super().fetch(ticker, market, period, range)

    with patch("investigraph.__main__.get_source", return_value=_CountingAdapter()):
        main(["AAPL", "--out", str(tmp_path / "a.html")])
        main(["AAPL", "--out", str(tmp_path / "b.html")])

    assert len(fetch_calls) == 1


def test_render_normalizes_lowercase_ticker(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "out.html"
    fetch_calls = []

    class _RecordingAdapter(_StubAdapter):
        def fetch(self, ticker, market, period, range):
            fetch_calls.append(ticker)
            return super().fetch(ticker, market, period, range)

    with patch("investigraph.__main__.get_source", return_value=_RecordingAdapter()):
        code = main(["aapl", "--out", str(out)])

    assert code == 0
    assert fetch_calls == ["AAPL"]
    assert out.name == "out.html"


def test_render_default_output_path_uses_normalized_ticker(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with patch("investigraph.__main__.get_source", return_value=_StubAdapter()):
        code = main(["aapl"])

    assert code == 0
    assert (tmp_path / "out" / "AAPL.html").exists()


def test_render_with_charts_flag_selects_only_named_charts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "out.html"

    with patch("investigraph.__main__.get_source", return_value=_StubAdapter()):
        code = main(["AAPL", "--charts", "price", "--out", str(out)])

    assert code == 0
    html = out.read_text()
    assert "<h3>Price</h3>" in html
    assert "<h3>Revenue</h3>" not in html


def test_render_with_duplicate_chart_ids_renders_each_chart_once(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "out.html"

    with patch("investigraph.__main__.get_source", return_value=_StubAdapter()):
        code = main(["AAPL", "--charts", "price,price", "--out", str(out)])

    assert code == 0
    assert out.read_text().count("<h3>Price</h3>") == 1


def test_render_with_unknown_chart_id_returns_error(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    code = main(
        [
            "AAPL",
            "--charts",
            "not-a-real-chart",
            "--out",
            str(tmp_path / "out.html"),
        ]
    )

    assert code == 1
    assert "unknown chart" in capsys.readouterr().err


def test_render_with_empty_charts_flag_returns_error(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    code = main(["AAPL", "--charts", " , ", "--out", str(tmp_path / "out.html")])

    assert code == 1
    assert "no charts specified" in capsys.readouterr().err


def test_render_with_unknown_chart_set_returns_error_without_fetching(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    fetch_calls = []

    class _CountingAdapter(_StubAdapter):
        def fetch(self, ticker, market, period, range):
            fetch_calls.append(ticker)
            return super().fetch(ticker, market, period, range)

    with patch("investigraph.__main__.get_source", return_value=_CountingAdapter()):
        code = main(
            [
                "AAPL",
                "--chart-set",
                "not-a-real-set",
                "--out",
                str(tmp_path / "out.html"),
            ]
        )

    assert code == 1
    assert "unknown chart set" in capsys.readouterr().err
    assert fetch_calls == []
    assert not (tmp_path / ".cache").exists()


def test_render_rejects_invalid_ticker(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    code = main(["../../etc/passwd", "--out", str(tmp_path / "out.html")])

    assert code == 1
    assert "invalid ticker" in capsys.readouterr().err


def test_render_rejects_unsupported_range(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["AAPL", "--range", "8y"])

    assert exc_info.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_render_rejects_a_period_the_source_does_not_declare(
    tmp_path, monkeypatch, capsys
):
    # Uses a stub source whose Capability declares only ANNUAL -- both real
    # sources (yfinance, twelvedata) declare TTM (derived, see
    # template/trailing.py); this exercises the generic pre-fetch gate itself,
    # not real TTM support.
    monkeypatch.chdir(tmp_path)
    fetch_calls = []

    class _CountingAdapter(_StubAdapter):
        def fetch(self, ticker, market, period, range):
            fetch_calls.append(ticker)
            return super().fetch(ticker, market, period, range)

    with patch("investigraph.__main__.get_source", return_value=_CountingAdapter()):
        code = main(["AAPL", "--period", "ttm", "--out", str(tmp_path / "out.html")])

    assert code == 1
    assert "does not support period ttm" in capsys.readouterr().err
    assert fetch_calls == []


def test_unrecognized_top_level_command_is_treated_as_ticker(
    tmp_path, monkeypatch, capsys
):
    # Documented residual limitation: a mistyped subcommand can't be told apart
    # from an unusual ticker without a mandatory verb, which would break the
    # documented `investigraph <TICKER> ...` invocation. This test pins
    # today's actual behavior rather than an aspirational one: "capabilites"
    # (a typo of "capabilities") is attempted as a fetch, not rejected as an
    # unknown command.
    monkeypatch.chdir(tmp_path)
    adapter = _StubAdapter(fetch_error=TickerNotFound("capabilites"))

    with patch("investigraph.__main__.get_source", return_value=adapter):
        code = main(["capabilites"])

    assert code == 1
    assert "not found" in capsys.readouterr().err


def test_help_lists_every_subcommand(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])

    out = capsys.readouterr().out
    assert "render" in out
    assert "verify-source" in out
    assert "capabilities" in out
    assert "commission-source" in out


def test_verify_source_subcommand_dispatches(monkeypatch, capsys):
    with patch("investigraph.__main__.get_source", return_value=_StubAdapter()):
        code = main(["verify-source", "yfinance", "--ticker", "AAPL"])

    assert code == 0
    assert "RESULT: clean" in capsys.readouterr().out


def test_capabilities_subcommand_prints_single_source(capsys):
    code = main(["capabilities", "yfinance"])

    assert code == 0
    out = capsys.readouterr().out
    assert "capabilities: yfinance" in out
    assert "price" in out


def test_capabilities_subcommand_prints_all_sources_when_no_name(capsys):
    code = main(["capabilities"])

    assert code == 0
    out = capsys.readouterr().out
    assert "capabilities: yfinance" in out
    assert "capabilities: twelvedata" in out


def test_capabilities_subcommand_unknown_source_returns_error(capsys):
    code = main(["capabilities", "not-a-real-source"])

    assert code == 1
    assert "unknown data source" in capsys.readouterr().err


def test_capabilities_matrix_flag_prints_table(capsys):
    code = main(["capabilities", "--matrix"])

    assert code == 0
    out = capsys.readouterr().out
    assert "capability matrix" in out
    assert "yfinance" in out
    assert "twelvedata" in out


def test_capabilities_requires_no_credentials(monkeypatch, capsys):
    monkeypatch.delenv("TWELVEDATA_API_KEY", raising=False)

    code = main(["capabilities", "twelvedata"])

    assert code == 0
    assert "capabilities: twelvedata" in capsys.readouterr().out


def _certificate() -> CommissionCertificate:
    return CommissionCertificate(
        source_name="yfinance",
        generated_at=date(2026, 1, 1),
        samples=(
            SampleResult(
                market=Market.US,
                company_type="large_cap",
                ticker="AAPL",
                period=Period.ANNUAL,
                ok=True,
                available_metrics=frozenset({"price"}),
            ),
        ),
        capability=Capability(
            markets={Market.US},
            periods={Period.ANNUAL},
            max_history={Period.ANNUAL: 4},
            metrics={"price"},
        ),
    )


def test_commission_source_subcommand_dispatches(tmp_path, capsys):
    written_path = tmp_path / "capability.py"
    adapter = _StubAdapter()

    with (
        patch("investigraph.__main__.get_source", return_value=adapter),
        patch(
            "investigraph.__main__.commission", return_value=_certificate()
        ) as mock_commission,
        patch(
            "investigraph.__main__.capability_module_path",
            return_value=written_path,
        ),
        patch(
            "investigraph.__main__.write_capability_module",
            return_value=written_path,
        ) as mock_write,
    ):
        code = main(["commission-source", "yfinance"])

    assert code == 0
    mock_commission.assert_called_once_with(adapter, "yfinance", range_="max")
    mock_write.assert_called_once_with(mock_commission.return_value)
    out = capsys.readouterr().out
    assert "commission-source: yfinance" in out
    assert "AAPL" in out
    assert "capabilities: yfinance" in out
    assert "overwriting" in out
    assert str(written_path) in out


def test_commission_source_forwards_range_flag(capsys):
    with (
        patch("investigraph.__main__.get_source", return_value=_StubAdapter()),
        patch(
            "investigraph.__main__.commission", return_value=_certificate()
        ) as mock_commission,
        patch("investigraph.__main__.capability_module_path"),
        patch("investigraph.__main__.write_capability_module"),
    ):
        main(["commission-source", "yfinance", "--range", "10y"])

    assert mock_commission.call_args.kwargs["range_"] == "10y"


def _degenerate_certificate() -> CommissionCertificate:
    return CommissionCertificate(
        source_name="yfinance",
        generated_at=date(2026, 1, 1),
        samples=(
            SampleResult(
                market=Market.US,
                company_type="large_cap",
                ticker="AAPL",
                period=Period.ANNUAL,
                ok=False,
                available_metrics=frozenset(),
                error="network error",
            ),
        ),
        capability=Capability(
            markets=set(),
            periods={Period.ANNUAL},
            max_history={},
            metrics=set(),
        ),
    )


def test_commission_source_refuses_to_write_a_degenerate_certificate(capsys):
    with (
        patch("investigraph.__main__.get_source", return_value=_StubAdapter()),
        patch(
            "investigraph.__main__.commission",
            return_value=_degenerate_certificate(),
        ),
        patch("investigraph.__main__.capability_module_path"),
        patch("investigraph.__main__.write_capability_module") as mock_write,
    ):
        code = main(["commission-source", "yfinance"])

    assert code == 1
    mock_write.assert_not_called()
    assert "refusing to overwrite" in capsys.readouterr().err


def test_commission_source_missing_credentials_returns_error(capsys):
    with patch(
        "investigraph.__main__.get_source",
        side_effect=MissingCredentials("TWELVEDATA_API_KEY is not set"),
    ):
        code = main(["commission-source", "twelvedata"])

    assert code == 1
    assert "TWELVEDATA_API_KEY" in capsys.readouterr().err


def test_commission_source_unknown_source_returns_error(capsys):
    code = main(["commission-source", "not-a-real-source"])

    assert code == 1
    assert "unknown data source" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# valuate
# ---------------------------------------------------------------------------


def _valuate_body(**overrides) -> dict:
    body = {
        "ok": True,
        "data": {
            "ticker": "AAPL",
            "currentPrice": 200.0,
            "currency": "USD",
            "epsTtm": 10.0,
            "asOf": "2026-08-28T00:00:00+00:00",
            "staleTtmWarning": False,
            "growth": {
                "historical1yPercent": 8.0,
                "historical3yPercent": 10.0,
                "historical5yPercent": None,
                "analystEstimate5yPercent": None,
                "epsTtmGrowthPercent": None,
            },
            "historicalPe": {"avg1y": 20.0, "avg3y": 22.0, "avg5y": None},
        },
        "effectiveEps": 10.0,
        "epsSource": "twelvedata",
        "epsSourceDetail": "Template TTM EPS ($10.00), as of 2025-09-30",
        "effectiveGrowth": 10.0,
        "bearGrowth": 7.5,
        "bullGrowth": 12.5,
        "lynch": {
            "base": {
                "ok": True,
                "fairValue": 100.0,
                "inputs": {
                    "epsTtm": 10.0,
                    "growthRatePercentRaw": 10.0,
                    "growthRatePercentClamped": 10.0,
                },
            },
            "bear": {"ok": False, "error": "NEGATIVE_GROWTH_RATE"},
            "bull": {"ok": True, "fairValue": 125.0, "inputs": {}},
        },
        "ruleOne": {
            "base": {
                "ok": True,
                "fairValue": 150.0,
                "inputs": {
                    "epsTtm": 10.0,
                    "growthRatePercentRaw": 10.0,
                    "growthRatePercentClamped": 10.0,
                    "exitPeMultiple": 15,
                    "requiredReturnPercent": 15,
                    "years": 10,
                    "mosPercent": 0,
                },
                "intermediate": {"stickerPrice": 150.0},
            },
            "bear": {"ok": True, "fairValue": 100.0, "inputs": {}},
            "bull": {"ok": True, "fairValue": 200.0, "inputs": {}},
        },
        "analystConsensus": None,
    }
    body.update(overrides)
    return body


def test_valuate_prints_fair_values(capsys):
    with patch(
        "investigraph.__main__.handle_valuate", return_value=_valuate_body()
    ) as mock_handle:
        code = main(["valuate", "AAPL"])

    assert code == 0
    mock_handle.assert_called_once_with(
        {
            "ticker": "AAPL",
            "exitPeMultiple": 15,
            "requiredReturnPercent": 15,
            "years": 10,
            "mosPercent": 0,
        }
    )
    out = capsys.readouterr().out
    assert "Ticker: AAPL" in out
    assert "Method A (Lynch) fair value: 100.00" in out
    assert "Method B (Rule #1) fair value: 150.00" in out


def test_valuate_shows_mos_and_sticker_price_when_mos_provided(capsys):
    body = _valuate_body()
    body["ruleOne"]["base"]["inputs"]["mosPercent"] = 25
    body["ruleOne"]["base"]["fairValue"] = 112.5
    with patch(
        "investigraph.__main__.handle_valuate", return_value=body
    ) as mock_handle:
        code = main(["valuate", "AAPL", "--mos", "25"])

    assert code == 0
    mock_handle.assert_called_once_with(
        {
            "ticker": "AAPL",
            "exitPeMultiple": 15,
            "requiredReturnPercent": 15,
            "years": 10,
            "mosPercent": 25.0,
        }
    )
    out = capsys.readouterr().out
    assert "MoS 25%" in out
    assert "Sticker: 150.00" in out


def test_valuate_shows_failed_method_with_error_code(capsys):
    body = _valuate_body()
    body["lynch"]["base"] = {"ok": False, "error": "MISSING_GROWTH_RATE"}
    with patch("investigraph.__main__.handle_valuate", return_value=body):
        code = main(["valuate", "AAPL"])

    assert code == 0
    assert (
        "Method A (Lynch) fair value: FAILED (MISSING_GROWTH_RATE)"
        in capsys.readouterr().out
    )


def test_valuate_shows_yahoo_fallback_source_note(capsys):
    body = _valuate_body(
        epsSource="yahoo-fallback",
        epsSourceDetail="Yahoo Finance trailing EPS ($8.71) -- used because ...",
    )
    with patch("investigraph.__main__.handle_valuate", return_value=body):
        code = main(["valuate", "AAPL"])

    assert code == 0
    out = capsys.readouterr().out
    assert "source: Yahoo Finance" in out
    assert "Yahoo Finance trailing EPS" in out


def test_valuate_error_from_service_prints_and_returns_1(capsys):
    from investigraph.web.valuate_service import ValuateError

    with patch(
        "investigraph.__main__.handle_valuate",
        side_effect=ValuateError(404, {"type": "NOT_FOUND", "ticker": "ZZZZ"}),
    ):
        code = main(["valuate", "ZZZZ"])

    assert code == 1
    assert "NOT_FOUND" in capsys.readouterr().err


def test_valuate_without_ticker_or_history_returns_error(capsys):
    code = main(["valuate"])

    assert code == 1
    assert "--history" in capsys.readouterr().err


def test_valuate_save_calls_create_valuation_with_camelcase_payload(capsys):
    with (
        patch("investigraph.__main__.handle_valuate", return_value=_valuate_body()),
        patch("investigraph.__main__.create_valuation") as mock_create,
    ):
        code = main(["valuate", "AAPL", "--save", "--notes", "thesis"])

    assert code == 0
    mock_create.assert_called_once_with(
        {
            "ticker": "AAPL",
            "currentPrice": 200.0,
            "currency": "USD",
            "epsTtm": 10.0,
            "growthRatePercent": 10.0,
            "exitPeMultiple": 15,
            "requiredReturnPercent": 15,
            "years": 10,
            "mosPercent": 0,
            "lynchFairValue": 100.0,
            "ruleOneFairValue": 150.0,
            "notes": "thesis",
        }
    )
    assert "saved to history" in capsys.readouterr().out


def test_valuate_save_skipped_when_growth_could_not_be_resolved(capsys):
    body = _valuate_body(effectiveGrowth=None)
    with (
        patch("investigraph.__main__.handle_valuate", return_value=body),
        patch("investigraph.__main__.create_valuation") as mock_create,
    ):
        code = main(["valuate", "AAPL", "--save"])

    assert code == 0
    mock_create.assert_not_called()


def test_valuate_history_flag_prints_formatted_table(capsys):
    records = [
        {
            "id": "1",
            "ticker": "AAPL",
            "evaluatedAt": "2026-08-19T10:00:00.000Z",
            "currentPrice": 220.0,
            "currency": "USD",
            "growthRatePercent": 12.0,
            "exitPeMultiple": 25.0,
            "requiredReturnPercent": 15.0,
            "years": 5,
            "lynchFairValue": 156.0,
            "ruleOneFairValue": 180.0,
            "mosPercent": 0,
            "notes": "",
        }
    ]
    with patch("investigraph.__main__.list_history", return_value=records) as mock_list:
        code = main(["valuate", "--history", "AAPL"])

    assert code == 0
    mock_list.assert_called_once_with("AAPL", None)
    out = capsys.readouterr().out
    assert "AAPL" in out
    assert "156.00" in out
    assert "180.00" in out


def test_valuate_history_empty_shows_a_clear_message(capsys):
    with patch("investigraph.__main__.list_history", return_value=[]):
        code = main(["valuate", "--history"])

    assert code == 0
    assert "No saved valuations found." in capsys.readouterr().out
