"""Yahoo consensus adapter: analyst price targets, next-year EPS growth consensus,
and a locally-computed Rule of 40, via `yfinance` (already a project dependency).

**Not a `DataSource`** (see `sources/base.py`): it does not produce a
`CompanyFundamentals` and must never be registered in `sources/registry.py` — that
registry assumes every entry declares a `Capability` and returns the canonical
template, which `capabilities`/`verify-source`/`commission-source` all rely on. This
is a sibling, independent module returning its own `AnalystConsensus` (see
`models.py`). A ticker with no analyst coverage (ETFs, some banks) or any
yfinance/network failure degrades to `None` — this module must never fail a
valuation that only needed Twelve Data/yfinance's own `CompanyFundamentals`.

Field mapping (yfinance -> `AnalystConsensus`), probed live against
AAPL/MS/JPM/BAC/IONQ/NVDA (see `adapter_test.py` for the guard cases this
uncovered — every field below has a real yfinance equivalent; none needed a
documented gap):

    next_year_eps_growth_percent  <- Ticker.growth_estimates.loc['+1y', 'stockTrend'] * 100
    price_target.{mean,high,low}  <- Ticker.info['target{Mean,High,Low}Price']
    price_target.number_of_analysts <- Ticker.info['numberOfAnalystOpinions']
    recommendation_key            <- Ticker.info['recommendationKey'] (can be the
                                      literal string "none", e.g. MS live — distinct
                                      from a missing/None value)
    beta                          <- Ticker.info['beta']
    price_to_sales                <- Ticker.info['priceToSalesTrailing12Months']
    trailing_eps                  <- Ticker.info['trailingEps']
    most_recent_quarter_end_date  <- Ticker.info['mostRecentQuarter'] (unix seconds)
    rule_of_40                    <- computed locally, see `_rule_of_40`

Two guards below were found against live data, not theorized — both are load-
bearing, do not "simplify" them away without re-checking the raw Yahoo fields
first (it has looked like a units bug before and wasn't one):

- `ebitdaMargins == 0` is untrustworthy unless the raw `ebitda` figure is present
  and >= 0. Confirmed live: MS/JPM/BAC (banks, no EBITDA concept) all report
  `ebitda: None, ebitdaMargins: 0.0`; IONQ reports `ebitda: -793_051_008` on
  ~$246M revenue yet still `ebitdaMargins: 0.0`. Trusting either 0 blindly
  previously fabricated a Rule of 40 score of 286.80 tagged "good" for IONQ.
- Revenue growth for Rule of 40 is derived from the two most recent *annual*
  points (`_annual_revenue_growth`), never `info["revenueGrowth"]` (Yahoo's
  quarterly YoY figure) — period-mismatched against the TTM `ebitdaMargins`.
  Confirmed live: NVDA's quarterly `revenueGrowth` was 105.9% vs. 65.47% true
  annual growth from the two most recent `financials` columns. Returns `None`
  with fewer than 2 valid annual points; deliberately no fallback to the
  mismatched quarterly figure.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timezone

import yfinance as yf

from investigraph.sources.yahoo_consensus.models import (
    AnalystConsensus,
    AnalystPriceTarget,
)


def fetch_analyst_consensus(ticker: str) -> AnalystConsensus | None:
    """Best-effort fetch. Any failure — unknown ticker, network error, no
    analyst coverage at all — degrades to `None` rather than raising; see the
    module docstring on why this must never fail a valuation.
    """
    try:
        return _fetch(ticker)
    except Exception:
        return None


def _fetch(ticker: str) -> AnalystConsensus | None:
    yf_ticker = yf.Ticker(ticker)
    info = yf_ticker.info
    if not info or len(info) <= 1:
        # Same "no usable data" signal `sources/yfinance/adapter.py` uses to
        # detect an unknown ticker.
        return None

    return AnalystConsensus(
        ticker=ticker,
        next_year_eps_growth_percent=_next_year_eps_growth_percent(yf_ticker),
        price_target=AnalystPriceTarget(
            mean=_as_float(info.get("targetMeanPrice")),
            high=_as_float(info.get("targetHighPrice")),
            low=_as_float(info.get("targetLowPrice")),
            number_of_analysts=_as_int(info.get("numberOfAnalystOpinions")),
        ),
        recommendation_key=info.get("recommendationKey"),
        beta=_as_float(info.get("beta")),
        price_to_sales=_as_float(info.get("priceToSalesTrailing12Months")),
        rule_of_40=_rule_of_40(yf_ticker, info),
        trailing_eps=_as_float(info.get("trailingEps")),
        most_recent_quarter_end_date=_most_recent_quarter_end_date(
            info.get("mostRecentQuarter")
        ),
        as_of=datetime.now(timezone.utc),
    )


def _next_year_eps_growth_percent(yf_ticker: yf.Ticker) -> float | None:
    # Auxiliary to an auxiliary: this whole module already degrades to `None` on
    # total failure (see `fetch_analyst_consensus`); this guard lets a failure
    # here specifically not take out the rest of an otherwise-successful fetch.
    try:
        estimates = yf_ticker.growth_estimates
    except Exception:
        return None
    if estimates is None or estimates.empty:
        return None
    if "+1y" not in estimates.index or "stockTrend" not in estimates.columns:
        return None
    growth = _as_float(estimates.loc["+1y", "stockTrend"])
    return growth * 100 if growth is not None else None


def _annual_revenue_growth(yf_ticker: yf.Ticker) -> float | None:
    """YoY growth fraction from the two most recent annual revenue points.

    See the module docstring's second guard: this must never fall back to
    `info["revenueGrowth"]` (quarterly, period-mismatched against the TTM
    `ebitdaMargins` `_rule_of_40` pairs it with).
    """
    try:
        financials = yf_ticker.financials
    except Exception:
        return None
    if (
        financials is None
        or financials.empty
        or "Total Revenue" not in financials.index
    ):
        return None

    row = financials.loc["Total Revenue"]
    valid_points = [
        (column, float(value))
        for column, value in row.items()
        if value is not None and not (isinstance(value, float) and math.isnan(value))
    ]
    if len(valid_points) < 2:
        return None

    valid_points.sort(key=lambda point: point[0])  # ascending by fiscal-year date
    (_, previous_revenue), (_, latest_revenue) = valid_points[-2], valid_points[-1]
    if previous_revenue == 0:
        return None
    return latest_revenue / previous_revenue - 1


def _rule_of_40(yf_ticker: yf.Ticker, info: dict) -> float | None:
    """`(annual revenue growth + ebitdaMargins) * 100` — both terms are
    fractions, so the single `* 100` is correct, not a double-conversion.

    See the module docstring's first guard for why a literal `ebitdaMargins ==
    0` is only trusted when the raw `ebitda` figure is present and >= 0.
    """
    ebitda_margins = _as_float(info.get("ebitdaMargins"))
    if ebitda_margins is None:
        return None

    ebitda = info.get("ebitda")
    ebitda_is_present_and_nonnegative = (
        ebitda is not None
        and not (isinstance(ebitda, float) and math.isnan(ebitda))
        and ebitda >= 0
    )
    margin_is_trustworthy = ebitda_margins != 0 or ebitda_is_present_and_nonnegative
    if not margin_is_trustworthy:
        return None

    annual_revenue_growth = _annual_revenue_growth(yf_ticker)
    if annual_revenue_growth is None:
        return None

    return (annual_revenue_growth + ebitda_margins) * 100


def _most_recent_quarter_end_date(raw: object) -> date | None:
    if raw is None:
        return None
    try:
        return datetime.fromtimestamp(int(raw), tz=timezone.utc).date()
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _as_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
