from datetime import date

from financial_charts.sources.base import Capability
from financial_charts.sources.verify import reconcile
from financial_charts.template.models import (
    CompanyFundamentals,
    Currency,
    Market,
    MetricSeries,
    Money,
    Period,
    Point,
    Unit,
)


class _StubAdapter:
    def __init__(self, capability: Capability, fundamentals: CompanyFundamentals):
        self._capability = capability
        self._fundamentals = fundamentals

    def capability(self) -> Capability:
        return self._capability

    def fetch(self, ticker, market, period, range) -> CompanyFundamentals:
        return self._fundamentals


def _money(value: float, currency: Currency = Currency.USD) -> Money:
    return Money(value=value, currency=currency, scale=Unit.ONES)


def test_clean_reconciliation_has_no_mismatch():
    capability = Capability(
        markets={Market.US},
        periods={Period.ANNUAL},
        max_history={Period.ANNUAL: 4},
        metrics={"price", "revenue"},
    )
    fundamentals = CompanyFundamentals(
        ticker="AAPL",
        market=Market.US,
        currency=Currency.USD,
        period=Period.ANNUAL,
        range="4y",
        series={
            "price": MetricSeries(
                metric_id="price",
                points=[Point(date=date(2026, 1, 1), value=_money(200))],
                available=True,
            ),
            "revenue": MetricSeries(
                metric_id="revenue",
                points=[Point(date=date(2026, 1, 1), value=_money(1_000_000))],
                available=True,
            ),
        },
    )

    report = reconcile(
        _StubAdapter(capability, fundamentals), "AAPL", Market.US, Period.ANNUAL, "4y"
    )

    assert report.missing_metrics == []
    assert report.undeclared_extras == []
    assert report.unit_warnings == []
    assert not report.has_mismatch


def test_declared_but_missing_metric_is_a_mismatch():
    capability = Capability(
        markets={Market.US},
        periods={Period.ANNUAL},
        max_history={Period.ANNUAL: 4},
        metrics={"price", "eps"},
    )
    fundamentals = CompanyFundamentals(
        ticker="AAPL",
        market=Market.US,
        currency=Currency.USD,
        period=Period.ANNUAL,
        range="4y",
        series={
            "price": MetricSeries(
                metric_id="price",
                points=[Point(date=date(2026, 1, 1), value=_money(200))],
                available=True,
            ),
            "eps": MetricSeries(metric_id="eps", points=[], available=False),
        },
    )

    report = reconcile(
        _StubAdapter(capability, fundamentals), "AAPL", Market.US, Period.ANNUAL, "4y"
    )

    assert report.missing_metrics == ["eps"]
    assert report.has_mismatch


def test_undeclared_extra_metric_is_reported_but_not_a_mismatch():
    capability = Capability(
        markets={Market.US},
        periods={Period.ANNUAL},
        max_history={Period.ANNUAL: 4},
        metrics={"price"},
    )
    fundamentals = CompanyFundamentals(
        ticker="AAPL",
        market=Market.US,
        currency=Currency.USD,
        period=Period.ANNUAL,
        range="4y",
        series={
            "price": MetricSeries(
                metric_id="price",
                points=[Point(date=date(2026, 1, 1), value=_money(200))],
                available=True,
            ),
            "eps": MetricSeries(
                metric_id="eps",
                points=[Point(date=date(2026, 1, 1), value=_money(6))],
                available=True,
            ),
        },
    )

    report = reconcile(
        _StubAdapter(capability, fundamentals), "AAPL", Market.US, Period.ANNUAL, "4y"
    )

    assert report.undeclared_extras == ["eps"]
    assert not report.has_mismatch


def _fundamentals_with_points(
    market: Market, metric_id: str, point_count: int, currency: Currency = Currency.USD
) -> CompanyFundamentals:
    return CompanyFundamentals(
        ticker="AAPL",
        market=market,
        currency=currency,
        period=Period.ANNUAL,
        range="max",
        series={
            metric_id: MetricSeries(
                metric_id=metric_id,
                points=[
                    Point(date=date(2000 + i, 1, 1), value=_money(1, currency))
                    for i in range(point_count)
                ],
                available=True,
            )
        },
    )


def test_short_history_is_a_mismatch_when_the_request_probed_the_full_declared_depth():
    # Declared 10y of annual history, but only 4 points (~4y) actually came back —
    # and the request was for "max", so the shortfall is attributable to the
    # source, not to a range smaller than what's declared.
    capability = Capability(
        markets={Market.US},
        periods={Period.ANNUAL},
        max_history={Period.ANNUAL: 10},
        metrics={"revenue"},
    )
    fundamentals = _fundamentals_with_points(Market.US, "revenue", 4)

    report = reconcile(
        _StubAdapter(capability, fundamentals), "AAPL", Market.US, Period.ANNUAL, "max"
    )

    assert len(report.history_warnings) == 1
    assert "revenue" in report.history_warnings[0]
    assert report.has_mismatch


def test_short_history_is_not_flagged_when_the_requested_range_is_smaller_than_declared():
    # Only asked for 1y even though 10y is declared — a short response here
    # doesn't prove the declaration is wrong, so it must not be flagged.
    capability = Capability(
        markets={Market.US},
        periods={Period.ANNUAL},
        max_history={Period.ANNUAL: 10},
        metrics={"revenue"},
    )
    fundamentals = _fundamentals_with_points(Market.US, "revenue", 1)

    report = reconcile(
        _StubAdapter(capability, fundamentals), "AAPL", Market.US, Period.ANNUAL, "1y"
    )

    assert report.history_warnings == []
    assert not report.has_mismatch


def test_price_depth_is_never_flagged_since_its_range_bounded_by_design():
    # price is deliberately excluded: its point count reflects the requested
    # --range (see both adapters), not the source's true max depth, unlike
    # the statement endpoints which return whatever depth the API gives
    # regardless of range.
    capability = Capability(
        markets={Market.US},
        periods={Period.ANNUAL},
        max_history={Period.ANNUAL: 10},
        metrics={"price"},
    )
    fundamentals = _fundamentals_with_points(Market.US, "price", 2)

    report = reconcile(
        _StubAdapter(capability, fundamentals), "AAPL", Market.US, Period.ANNUAL, "max"
    )

    assert report.history_warnings == []


def test_unconverted_agorot_price_triggers_unit_warning():
    capability = Capability(
        markets={Market.TASE},
        periods={Period.ANNUAL},
        max_history={Period.ANNUAL: 4},
        metrics={"price"},
    )
    fundamentals = CompanyFundamentals(
        ticker="TEVA.TA",
        market=Market.TASE,
        currency=Currency.ILS,
        period=Period.ANNUAL,
        range="4y",
        series={
            "price": MetricSeries(
                metric_id="price",
                # A raw agorot quote left unconverted (should have been /100).
                points=[
                    Point(date=date(2026, 1, 1), value=_money(973_500, Currency.ILS))
                ],
                available=True,
            ),
        },
    )

    report = reconcile(
        _StubAdapter(capability, fundamentals),
        "TEVA.TA",
        Market.TASE,
        Period.ANNUAL,
        "4y",
    )

    assert len(report.unit_warnings) == 1
    assert "agorot" in report.unit_warnings[0]
    # verify-source exists specifically to catch this TASE gotcha — a detected
    # unit warning must fail the reconciliation, not just be printed as a note.
    assert report.has_mismatch


def _fundamentals_with_revenue(
    market: Market, value: float, currency: Currency = Currency.ILS
) -> CompanyFundamentals:
    return CompanyFundamentals(
        ticker="EXMP.TA" if market == Market.TASE else "EXMP",
        market=market,
        currency=Currency.ILS if market == Market.TASE else Currency.USD,
        period=Period.ANNUAL,
        range="4y",
        series={
            "revenue": MetricSeries(
                metric_id="revenue",
                points=[Point(date=date(2026, 1, 1), value=_money(value, currency))],
                available=True,
            ),
        },
    )


def test_tase_revenue_scaled_down_too_far_triggers_unit_warning():
    # A revenue figure that should be in the hundreds of millions of shekels,
    # left at a raw few hundred — the "millions of shekels" half of the TASE
    # unit trap, e.g. a source that reports pre-scaled figures the adapter
    # never multiplied back up.
    capability = Capability(
        markets={Market.TASE},
        periods={Period.ANNUAL},
        max_history={Period.ANNUAL: 4},
        metrics={"revenue"},
    )
    fundamentals = _fundamentals_with_revenue(Market.TASE, 500, Currency.ILS)

    report = reconcile(
        _StubAdapter(capability, fundamentals),
        "EXMP.TA",
        Market.TASE,
        Period.ANNUAL,
        "4y",
    )

    assert len(report.unit_warnings) == 1
    assert "revenue" in report.unit_warnings[0]
    assert report.has_mismatch


def test_tase_revenue_at_a_plausible_magnitude_is_not_flagged():
    capability = Capability(
        markets={Market.TASE},
        periods={Period.ANNUAL},
        max_history={Period.ANNUAL: 4},
        metrics={"revenue"},
    )
    fundamentals = _fundamentals_with_revenue(Market.TASE, 500_000_000, Currency.ILS)

    report = reconcile(
        _StubAdapter(capability, fundamentals),
        "EXMP.TA",
        Market.TASE,
        Period.ANNUAL,
        "4y",
    )

    assert report.unit_warnings == []


def test_tase_revenue_denominated_in_usd_is_not_shekel_magnitude_checked():
    # A dual-currency TASE company (e.g. Teva: ILS price, USD statements) —
    # the shekel-magnitude heuristic must not apply to a non-ILS statement.
    capability = Capability(
        markets={Market.TASE},
        periods={Period.ANNUAL},
        max_history={Period.ANNUAL: 4},
        metrics={"revenue"},
    )
    fundamentals = _fundamentals_with_revenue(Market.TASE, 500, Currency.USD)

    report = reconcile(
        _StubAdapter(capability, fundamentals),
        "EXMP.TA",
        Market.TASE,
        Period.ANNUAL,
        "4y",
    )

    assert report.unit_warnings == []


def test_us_market_revenue_is_never_shekel_magnitude_checked():
    capability = Capability(
        markets={Market.US},
        periods={Period.ANNUAL},
        max_history={Period.ANNUAL: 4},
        metrics={"revenue"},
    )
    fundamentals = _fundamentals_with_revenue(Market.US, 500, Currency.USD)

    report = reconcile(
        _StubAdapter(capability, fundamentals), "EXMP", Market.US, Period.ANNUAL, "4y"
    )

    assert report.unit_warnings == []
