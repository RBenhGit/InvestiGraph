from datetime import date

from investigraph.sources.base import Capability, SourceUnavailable, TickerNotFound
from investigraph.sources.commission import (
    SAMPLE_TICKERS,
    CommissionCertificate,
    SampleResult,
    candidate_metrics,
    commission,
    is_degenerate,
    write_capability_module,
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


def _series(metric_id: str, available: bool = True, points: int = 3) -> MetricSeries:
    return MetricSeries(
        metric_id=metric_id,
        points=(
            [
                Point(
                    date=date(2020 + i, 1, 1),
                    value=Money(value=1.0, currency=Currency.USD, scale=Unit.ONES),
                )
                for i in range(points)
            ]
            if available
            else []
        ),
        available=available,
    )


def _fundamentals(
    ticker: str, market: Market, period: Period, series: dict[str, MetricSeries]
) -> CompanyFundamentals:
    return CompanyFundamentals(
        ticker=ticker,
        market=market,
        currency=Currency.USD if market == Market.US else Currency.ILS,
        period=period,
        range="max",
        series=series,
    )


class _StubAdapter:
    def __init__(self, by_key):
        self._by_key = by_key  # (ticker, period) -> CompanyFundamentals | Exception

    def capability(self):
        raise AssertionError(
            "commission() must not consult the adapter's self-reported capability"
        )

    def fetch(self, ticker, market, period, range_):
        result = self._by_key[(ticker, period)]
        if isinstance(result, Exception):
            raise result
        return result


def test_candidate_metrics_matches_catalog_required_metrics_not_derived_ids():
    metrics = candidate_metrics()

    assert "price" in metrics
    assert "revenue" in metrics
    assert "fcf_margin" not in metrics  # a derived quantity, never source-supplied


def test_commission_declares_only_metrics_common_to_every_sample():
    sample_tickers = {Market.US: {"bank": "BANK", "large_cap": "BIG"}}
    by_key = {
        ("BANK", Period.ANNUAL): _fundamentals(
            "BANK",
            Market.US,
            Period.ANNUAL,
            {"price": _series("price"), "revenue": _series("revenue", available=False)},
        ),
        ("BANK", Period.QUARTERLY): _fundamentals(
            "BANK",
            Market.US,
            Period.QUARTERLY,
            {"price": _series("price"), "revenue": _series("revenue", available=False)},
        ),
        ("BIG", Period.ANNUAL): _fundamentals(
            "BIG",
            Market.US,
            Period.ANNUAL,
            {"price": _series("price"), "revenue": _series("revenue")},
        ),
        ("BIG", Period.QUARTERLY): _fundamentals(
            "BIG",
            Market.US,
            Period.QUARTERLY,
            {"price": _series("price"), "revenue": _series("revenue")},
        ),
    }
    adapter = _StubAdapter(by_key)

    certificate = commission(adapter, "teststub", sample_tickers=sample_tickers)

    assert "price" in certificate.capability.metrics
    assert "revenue" not in certificate.capability.metrics  # bank sample lacked it
    assert certificate.capability.markets == {Market.US}


def test_sample_tickers_has_at_least_one_entry_per_market():
    # A market key with an empty inner dict would be silently declared
    # supported by commission() without ever being probed (see the test
    # below) — pin the shipped table's shape so that can't happen unnoticed.
    for market, tickers_by_type in SAMPLE_TICKERS.items():
        assert tickers_by_type, f"{market} has no sample tickers"


def test_commission_skips_a_market_with_no_sample_tickers():
    sample_tickers = {Market.US: {}}
    adapter = _StubAdapter({})

    certificate = commission(adapter, "teststub", sample_tickers=sample_tickers)

    assert certificate.capability.markets == set()
    assert certificate.samples == ()


def test_commission_excludes_a_market_when_a_sample_fetch_fails():
    sample_tickers = {
        Market.US: {"large_cap": "BIG"},
        Market.TASE: {"large_cap": "FAIL.TA"},
    }
    by_key = {
        ("BIG", Period.ANNUAL): _fundamentals(
            "BIG", Market.US, Period.ANNUAL, {"price": _series("price")}
        ),
        ("BIG", Period.QUARTERLY): _fundamentals(
            "BIG", Market.US, Period.QUARTERLY, {"price": _series("price")}
        ),
        ("FAIL.TA", Period.ANNUAL): TickerNotFound("FAIL.TA"),
        ("FAIL.TA", Period.QUARTERLY): TickerNotFound("FAIL.TA"),
    }
    adapter = _StubAdapter(by_key)

    certificate = commission(adapter, "teststub", sample_tickers=sample_tickers)

    assert certificate.capability.markets == {Market.US}
    failed = [s for s in certificate.samples if not s.ok]
    assert len(failed) == 2
    assert all(s.market == Market.TASE for s in failed)


def test_commission_excludes_a_market_when_price_is_unavailable():
    sample_tickers = {Market.US: {"large_cap": "NODATA"}}
    by_key = {
        ("NODATA", Period.ANNUAL): _fundamentals(
            "NODATA",
            Market.US,
            Period.ANNUAL,
            {"price": _series("price", available=False)},
        ),
        ("NODATA", Period.QUARTERLY): _fundamentals(
            "NODATA",
            Market.US,
            Period.QUARTERLY,
            {"price": _series("price", available=False)},
        ),
    }
    adapter = _StubAdapter(by_key)

    certificate = commission(adapter, "teststub", sample_tickers=sample_tickers)

    assert certificate.capability.markets == set()


def test_commission_treats_source_unavailable_like_ticker_not_found():
    sample_tickers = {Market.US: {"large_cap": "DOWN"}}
    by_key = {
        ("DOWN", Period.ANNUAL): SourceUnavailable("network error"),
        ("DOWN", Period.QUARTERLY): SourceUnavailable("network error"),
    }
    adapter = _StubAdapter(by_key)

    certificate = commission(adapter, "teststub", sample_tickers=sample_tickers)

    assert certificate.capability.markets == set()
    assert all(not s.ok for s in certificate.samples)


def test_commission_derives_conservative_max_history():
    # price is excluded from the depth calculation (RANGE_BOUNDED_METRICS) --
    # daily cadence, not a fair comparison against approx_years' annual/quarterly
    # assumption -- so revenue is the depth signal here, matching what the real
    # source adapters' statement metrics look like.
    sample_tickers = {Market.US: {"large_cap": "BIG", "small_cap": "SMALL"}}
    by_key = {
        ("BIG", Period.ANNUAL): _fundamentals(
            "BIG",
            Market.US,
            Period.ANNUAL,
            {"price": _series("price"), "revenue": _series("revenue", points=10)},
        ),
        ("BIG", Period.QUARTERLY): _fundamentals(
            "BIG",
            Market.US,
            Period.QUARTERLY,
            {"price": _series("price"), "revenue": _series("revenue", points=40)},
        ),
        ("SMALL", Period.ANNUAL): _fundamentals(
            "SMALL",
            Market.US,
            Period.ANNUAL,
            {"price": _series("price"), "revenue": _series("revenue", points=3)},
        ),
        ("SMALL", Period.QUARTERLY): _fundamentals(
            "SMALL",
            Market.US,
            Period.QUARTERLY,
            {"price": _series("price"), "revenue": _series("revenue", points=8)},
        ),
    }
    adapter = _StubAdapter(by_key)

    certificate = commission(adapter, "teststub", sample_tickers=sample_tickers)

    assert certificate.capability.max_history[Period.ANNUAL] == 3  # min(10, 3)
    assert certificate.capability.max_history[Period.QUARTERLY] == 2  # min(10, 2)


def test_commission_max_history_uses_best_metric_per_sample_not_worst():
    # A single naturally sparse metric on one ticker (e.g. a small-cap that
    # skipped a dividend one quarter) must not drag the whole declaration's
    # depth down when that same ticker's other metrics prove the source
    # returns more -- this was the bug behind a real yfinance commission-source
    # run declaring 0 years of quarterly history off one thin dividends_paid
    # series, despite every other metric having ample depth.
    sample_tickers = {Market.US: {"large_cap": "BIG"}}
    by_key = {
        ("BIG", Period.ANNUAL): _fundamentals(
            "BIG",
            Market.US,
            Period.ANNUAL,
            {"price": _series("price"), "revenue": _series("revenue", points=10)},
        ),
        ("BIG", Period.QUARTERLY): _fundamentals(
            "BIG",
            Market.US,
            Period.QUARTERLY,
            {
                "price": _series("price"),
                "revenue": _series("revenue", points=20),
                "dividends_paid": _series("dividends_paid", points=3),
            },
        ),
    }
    adapter = _StubAdapter(by_key)

    certificate = commission(adapter, "teststub", sample_tickers=sample_tickers)

    # 20 revenue points -> 5y, not 3 dividends_paid points -> 0y.
    assert certificate.capability.max_history[Period.QUARTERLY] == 5


def test_commission_adds_ttm_at_quarterly_depth_when_quarterly_is_supported():
    # No adapter fetches Period.TTM natively -- template/trailing.py's
    # derive_ttm_fundamentals derives it from QUARTERLY in every adapter
    # unconditionally -- so commission() must never probe TTM directly, and
    # must instead add it after the fact at QUARTERLY's own depth once
    # QUARTERLY itself qualifies.
    sample_tickers = {Market.US: {"large_cap": "BIG"}}
    by_key = {
        ("BIG", Period.ANNUAL): _fundamentals(
            "BIG",
            Market.US,
            Period.ANNUAL,
            {"price": _series("price"), "revenue": _series("revenue", points=10)},
        ),
        ("BIG", Period.QUARTERLY): _fundamentals(
            "BIG",
            Market.US,
            Period.QUARTERLY,
            {"price": _series("price"), "revenue": _series("revenue", points=20)},
        ),
    }
    adapter = _StubAdapter(by_key)

    certificate = commission(adapter, "teststub", sample_tickers=sample_tickers)

    assert Period.TTM in certificate.capability.periods
    assert (
        certificate.capability.max_history[Period.TTM]
        == certificate.capability.max_history[Period.QUARTERLY]
    )
    # TTM was never actually probed -- no sample in the certificate names it.
    assert all(sample.period != Period.TTM for sample in certificate.samples)


def test_commission_omits_ttm_when_quarterly_was_never_probed():
    sample_tickers = {Market.US: {"large_cap": "BIG"}}
    by_key = {
        ("BIG", Period.ANNUAL): _fundamentals(
            "BIG",
            Market.US,
            Period.ANNUAL,
            {"price": _series("price"), "revenue": _series("revenue")},
        ),
    }
    adapter = _StubAdapter(by_key)

    certificate = commission(
        adapter, "teststub", sample_tickers=sample_tickers, periods=(Period.ANNUAL,)
    )

    assert Period.TTM not in certificate.capability.periods
    assert Period.TTM not in certificate.capability.max_history


def test_is_degenerate_true_when_samples_exist_but_no_market_qualified():
    certificate = CommissionCertificate(
        source_name="teststub",
        generated_at=date(2026, 1, 1),
        samples=(
            SampleResult(
                market=Market.US,
                company_type="large_cap",
                ticker="BIG",
                period=Period.ANNUAL,
                ok=False,
                available_metrics=frozenset(),
                error="network error",
            ),
        ),
        capability=Capability(
            markets=set(), periods={Period.ANNUAL}, max_history={}, metrics=set()
        ),
    )

    assert is_degenerate(certificate)


def test_is_degenerate_false_when_no_samples_were_ever_attempted():
    # A market with no configured sample tickers is a deliberate skip, not a
    # failure — must not be flagged the same as a wholesale outage.
    certificate = CommissionCertificate(
        source_name="teststub",
        generated_at=date(2026, 1, 1),
        samples=(),
        capability=Capability(
            markets=set(), periods={Period.ANNUAL}, max_history={}, metrics=set()
        ),
    )

    assert not is_degenerate(certificate)


def test_is_degenerate_false_for_a_healthy_certificate():
    certificate = CommissionCertificate(
        source_name="teststub",
        generated_at=date(2026, 1, 1),
        samples=(
            SampleResult(
                market=Market.US,
                company_type="large_cap",
                ticker="BIG",
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

    assert not is_degenerate(certificate)


def test_write_capability_module_generates_valid_reloadable_python(tmp_path):
    certificate = CommissionCertificate(
        source_name="testsource",
        generated_at=date(2026, 1, 1),
        samples=(),
        capability=Capability(
            markets={Market.US},
            periods={Period.ANNUAL},
            max_history={Period.ANNUAL: 7},
            metrics={"price", "revenue"},
        ),
    )

    path = write_capability_module(certificate, base_dir=tmp_path)

    assert path == tmp_path / "testsource" / "capability.py"
    namespace: dict = {}
    exec(path.read_text(), namespace)
    assert namespace["CAPABILITY"] == certificate.capability


def test_write_capability_module_escapes_an_unusual_metric_id(tmp_path):
    # A metric id containing a quote must still produce valid, reloadable
    # Python — proves repr() is doing real escaping, not just formatting.
    certificate = CommissionCertificate(
        source_name="testsource",
        generated_at=date(2026, 1, 1),
        samples=(),
        capability=Capability(
            markets={Market.US},
            periods={Period.ANNUAL},
            max_history={Period.ANNUAL: 1},
            metrics={'weird"metric'},
        ),
    )

    path = write_capability_module(certificate, base_dir=tmp_path)

    namespace: dict = {}
    exec(path.read_text(), namespace)
    assert namespace["CAPABILITY"] == certificate.capability
