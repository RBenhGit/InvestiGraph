from datetime import date, datetime, timezone

import pytest

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
from investigraph.valuation.resolve_eps import resolve_eps


def _money(value: float) -> Money:
    return Money(value=value, currency=Currency.USD, scale=Unit.ONES)


def _annual_fundamentals(latest_eps: float, as_of: date = date(2025, 9, 30)):
    return CompanyFundamentals(
        ticker="AAPL",
        market=Market.US,
        currency=Currency.USD,
        period=Period.ANNUAL,
        range="5y",
        series={
            "eps": MetricSeries(
                metric_id="eps",
                points=[
                    Point(date=date(2024, 9, 30), value=_money(latest_eps - 1.0)),
                    Point(date=as_of, value=_money(latest_eps)),
                ],
                available=True,
            )
        },
    )


def _no_eps_fundamentals():
    return CompanyFundamentals(
        ticker="AAPL",
        market=Market.US,
        currency=Currency.USD,
        period=Period.ANNUAL,
        range="5y",
        series={},
    )


def _consensus(
    trailing_eps: float | None,
    most_recent_quarter_end_date: date | None = None,
) -> AnalystConsensus:
    return AnalystConsensus(
        ticker="AAPL",
        price_target=AnalystPriceTarget(),
        trailing_eps=trailing_eps,
        most_recent_quarter_end_date=most_recent_quarter_end_date,
        as_of=datetime.now(timezone.utc),
    )


def test_no_consensus_uses_the_template_figure_as_is():
    resolved = resolve_eps(_annual_fundamentals(8.71), None)

    assert resolved is not None
    assert resolved.eps_ttm == 8.71
    assert resolved.source == "twelvedata"
    assert "8.71" in resolved.detail


def test_consensus_present_but_no_trailing_eps_cannot_detect_staleness_uses_template():
    resolved = resolve_eps(_annual_fundamentals(8.71), _consensus(trailing_eps=None))

    assert resolved is not None
    assert resolved.source == "twelvedata"
    assert resolved.eps_ttm == 8.71


def test_small_divergence_from_yahoo_is_not_flagged_stale():
    # (8.75 - 8.71) / 8.75 ≈ 0.46% — well under the 5% threshold.
    resolved = resolve_eps(_annual_fundamentals(8.71), _consensus(trailing_eps=8.75))

    assert resolved is not None
    assert resolved.source == "twelvedata"
    assert resolved.eps_ttm == 8.71


def test_large_divergence_falls_back_to_a_positive_yahoo_figure():
    # (8.71 - 7.0) / 7.0 ≈ 24.4% — flagged stale; Yahoo's figure is usable.
    resolved = resolve_eps(
        _annual_fundamentals(8.71),
        _consensus(trailing_eps=7.0, most_recent_quarter_end_date=date(2026, 6, 27)),
    )

    assert resolved is not None
    assert resolved.source == "yahoo-fallback"
    assert resolved.eps_ttm == 7.0
    assert "2026-06-27" in resolved.detail
    # The UI must never show a Yahoo-sourced number as if it came from Twelve Data.
    assert "twelvedata" not in resolved.detail.lower()
    # template_eps_ttm stays the raw, pre-resolution figure even on a Yahoo
    # fallback -- distinct from eps_ttm (7.0) above, which is Yahoo's figure here.
    assert resolved.template_eps_ttm == 8.71


def test_large_divergence_with_a_non_positive_yahoo_figure_keeps_template_flagged():
    # Yahoo's own figure is negative (a real loss-making trailing year, e.g. IONQ) —
    # not usable as a shown replacement even though it triggered the divergence.
    resolved = resolve_eps(_annual_fundamentals(8.71), _consensus(trailing_eps=-3.87))

    assert resolved is not None
    assert resolved.source == "twelvedata-stale-no-fallback"
    assert resolved.eps_ttm == 8.71
    assert "stale" in resolved.detail.lower()


def test_yahoo_eps_of_exactly_zero_cannot_support_a_relative_comparison_not_stale():
    resolved = resolve_eps(_annual_fundamentals(8.71), _consensus(trailing_eps=0.0))

    assert resolved is not None
    assert resolved.source == "twelvedata"


def test_returns_none_when_the_template_has_no_usable_eps_at_all():
    assert resolve_eps(_no_eps_fundamentals(), _consensus(trailing_eps=8.71)) is None


def test_detail_date_reflects_the_ttm_window_actually_used_not_the_newest_raw_point():
    # Regression: an interior gap (2026-06-30 missing) means the two newest raw
    # points (2026-09-30, 2026-12-31) can't complete a 4-quarter window with
    # anything else in range — `ttm_series` skips both windows that would need
    # them. The only surviving TTM point is dated 2026-03-31. The `detail`
    # string's date must reflect that TTM point, not the newest *raw* eps point
    # (2026-12-31), which would misrepresent what the shown number covers.
    fundamentals = CompanyFundamentals(
        ticker="AAPL",
        market=Market.US,
        currency=Currency.USD,
        period=Period.QUARTERLY,
        range="5y",
        series={
            "eps": MetricSeries(
                metric_id="eps",
                points=[
                    Point(date=date(2025, 6, 30), value=_money(2.0)),
                    Point(date=date(2025, 9, 30), value=_money(2.0)),
                    Point(date=date(2025, 12, 31), value=_money(2.0)),
                    Point(date=date(2026, 3, 31), value=_money(2.0)),
                    # date(2026, 6, 30) missing
                    Point(date=date(2026, 9, 30), value=_money(2.5)),
                    Point(date=date(2026, 12, 31), value=_money(3.0)),
                ],
                available=True,
            )
        },
    )

    resolved = resolve_eps(fundamentals, None)

    assert resolved is not None
    assert resolved.eps_ttm == pytest.approx(8.0)
    assert "2026-03-31" in resolved.detail
    assert "2026-12-31" not in resolved.detail


# Regression (found in the convergence review before Phase 7): a dual-listed company can
# legitimately report financials in a different currency than the one its shares trade in
# (e.g. a TASE ticker filing in USD while quoted in ILS) -- eps's Money carries that
# statement currency, distinct from fundamentals.currency (the market/price currency).
# Unwrapping the Money with as_base_units() silently dropped this, so a USD eps and an ILS
# price could combine into a nonsense fair value with no error or warning.


def test_returns_none_when_eps_currency_does_not_match_fundamentals_currency():
    mismatched = CompanyFundamentals(
        ticker="TEVA.TA",
        market=Market.US,
        currency=Currency.ILS,  # the market/price currency
        period=Period.ANNUAL,
        range="5y",
        series={
            "eps": MetricSeries(
                metric_id="eps",
                points=[
                    # eps itself is tagged USD -- the statement currency, deliberately
                    # different from fundamentals.currency above.
                    Point(date=date(2024, 9, 30), value=_money(3.0)),
                    Point(date=date(2025, 9, 30), value=_money(3.5)),
                ],
                available=True,
            )
        },
    )

    assert resolve_eps(mismatched, _consensus(trailing_eps=3.5)) is None


def test_resolved_eps_carries_the_currency_it_is_actually_in():
    resolved = resolve_eps(_annual_fundamentals(8.71), None)

    assert resolved is not None
    assert resolved.currency == Currency.USD


def test_works_against_a_quarterly_period_fetch_via_ttm_series():
    fundamentals = CompanyFundamentals(
        ticker="AAPL",
        market=Market.US,
        currency=Currency.USD,
        period=Period.QUARTERLY,
        range="5y",
        series={
            "eps": MetricSeries(
                metric_id="eps",
                points=[
                    Point(date=date(2025, 3, 31), value=_money(2.0)),
                    Point(date=date(2025, 6, 30), value=_money(2.1)),
                    Point(date=date(2025, 9, 30), value=_money(2.2)),
                    Point(date=date(2025, 12, 31), value=_money(2.3)),
                ],
                available=True,
            )
        },
    )

    resolved = resolve_eps(fundamentals, None)

    assert resolved is not None
    assert resolved.eps_ttm == 2.0 + 2.1 + 2.2 + 2.3
    assert resolved.source == "twelvedata"
