"""Orchestration for `POST /api/valuate`, composed only from published interfaces
(`valuation/`, `sources/yahoo_consensus/`, `sources/market.py`, `web/service.py`).

Ported from Eps_Evaluation's `POST /api/valuate` handler
(legacy/eps_evaluation/src/web/server.ts) onto Financial_Charts' canonical
`CompanyFundamentals` template. Contract pinned by `server.test.ts`; see
`docs/MERGE_SPEC.md` Phase 7.

**Always fetches `Period.ANNUAL`, independent of whatever period a chart-grid
request on the same page might use.** `valuation/growth.py`'s historical CAGR
functions only return non-`None` for annual fundamentals, and
`analyst_estimate_5y_percent` is permanently `None` in this merge (see that
module's docstring) — a quarterly/TTM fetch would collapse the whole growth
chain to `MISSING_GROWTH_RATE` for every scenario. Found in the Phase 4-6
convergence review, before this module existed; fixed here at the point the
gap would otherwise have been introduced, not after.

`forceRefresh` (accepted from the request body, matching the original's field
name) is currently a no-op: `web/service.py`'s `load_fundamentals` has no
cache-bypass option (`TemplateCache` is unconditionally cache-first). Wiring
a real bypass would mean changing `cache/store.py`/`web/service.py`, both
outside this module's scope — flagged here rather than silently dropped.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from investigraph import config
from investigraph.sources.base import (
    MissingCredentials,
    SourceUnavailable,
    TickerNotFound,
    UnsupportedPeriod,
)
from investigraph.sources.market import is_valid_ticker, normalize_ticker
from investigraph.sources.yahoo_consensus.adapter import fetch_analyst_consensus
from investigraph.sources.yahoo_consensus.models import AnalystConsensus
from investigraph.template.models import CompanyFundamentals, Money, Period
from investigraph.valuation.growth import (
    calculate_ttm_eps_growth_percent,
    historical_1y_growth_percent,
    historical_3y_growth_percent,
    historical_5y_growth_percent,
    resolve_growth_rate_percent,
)
from investigraph.valuation.historical_pe import compute_historical_pe_averages
from investigraph.valuation.resolve_eps import ResolvedEps, resolve_eps
from investigraph.valuation.rule_one.calculate import (
    RuleOneInputsUsed,
    calculate_rule_one_value,
)
from investigraph.valuation.shared.types import ValuationErr, ValuationOk
from investigraph.web.service import load_fundamentals


@dataclass
class ValuateError(Exception):
    """Raised for any request that must produce a non-200 `{ok: false, error}`
    response. `status` is the HTTP status; `error` is the typed error dict,
    matching the original's `StockDataError` shape closely enough for
    `formatStockDataError` (app.js) to render something sensible — Financial_
    Charts' adapters raise a different exception vocabulary than Eps_
    Evaluation's Twelve Data client did, so this is a mapping, not a literal
    port of the same error types.
    """

    status: int
    error: dict[str, Any]


def handle_valuate(payload: dict[str, Any]) -> dict[str, Any]:
    """Build the full `/api/valuate` response body for a valid request.

    Raises `ValuateError` for anything that must be a non-200 response. The
    Flask route (`web/app.py`) catches that and returns `(jsonify(ok=False,
    error=exc.error), exc.status)` — this function only ever returns the
    `ok: true` body.
    """
    ticker = _validated_ticker(payload)
    source_name = config.data_source_name()

    fundamentals = _load_fundamentals_or_raise(ticker, source_name)
    consensus = _fetch_consensus_best_effort(ticker)

    resolved = resolve_eps(fundamentals, consensus)
    if resolved is None:
        raise ValuateError(
            400,
            {
                "type": "INSUFFICIENT_DATA",
                "ticker": ticker,
                "reason": "unable to resolve TTM EPS",
            },
        )

    current_price = _current_price_or_raise(fundamentals, ticker)

    eps_override = payload.get("epsOverride")
    effective_eps = (
        eps_override
        if isinstance(eps_override, (int, float)) and eps_override > 0
        else resolved.eps_ttm
    )
    eps_source = (
        None
        if isinstance(eps_override, (int, float)) and eps_override > 0
        else resolved.source
    )

    effective_growth = _as_optional_number(payload.get("growthRatePercent"))
    if effective_growth is None:
        effective_growth = resolve_growth_rate_percent(
            analyst_estimate_5y_percent=None,  # no source in this merge, see growth.py
            historical_3y_percent=historical_3y_growth_percent(fundamentals),
            historical_1y_percent=historical_1y_growth_percent(fundamentals),
        )

    mos_percent = payload.get("mosPercent") or 0

    rule_one_base = calculate_rule_one_value(
        effective_eps,
        effective_growth,
        payload.get("exitPeMultiple"),
        payload.get("requiredReturnPercent"),
        payload.get("years"),
        mos_percent,
    )

    bear_growth = _scenario_growth(
        payload.get("bearGrowthRatePercent"), effective_growth, bear=True
    )
    rule_one_bear = calculate_rule_one_value(
        effective_eps,
        bear_growth,
        _or_default(payload.get("bearExitPeMultiple"), 10),
        _or_default(payload.get("bearRequiredReturnPercent"), 15),
        payload.get("years"),
        mos_percent,
    )

    bull_growth = _scenario_growth(
        payload.get("bullGrowthRatePercent"), effective_growth, bear=False
    )
    rule_one_bull = calculate_rule_one_value(
        effective_eps,
        bull_growth,
        _or_default(payload.get("bullExitPeMultiple"), 20),
        _or_default(payload.get("bullRequiredReturnPercent"), 12),
        payload.get("years"),
        mos_percent,
    )

    return {
        "ok": True,
        "data": _serialize_data(fundamentals, resolved, current_price),
        "effectiveEps": effective_eps,
        "epsSource": eps_source,
        "epsSourceDetail": resolved.detail,
        "effectiveGrowth": effective_growth,
        "bearGrowth": bear_growth,
        "bullGrowth": bull_growth,
        "ruleOne": {
            "base": _serialize_result(rule_one_base),
            "bear": _serialize_result(rule_one_bear),
            "bull": _serialize_result(rule_one_bull),
        },
        "analystConsensus": _serialize_consensus(consensus),
    }


def _validated_ticker(payload: dict[str, Any]) -> str:
    ticker = payload.get("ticker")
    if not isinstance(ticker, str) or not ticker.strip():
        raise ValuateError(
            400,
            {
                "type": "INSUFFICIENT_DATA",
                "ticker": ticker if isinstance(ticker, str) else "",
                "reason": "ticker is required and must be a non-empty string",
            },
        )
    ticker = ticker.strip()
    if not is_valid_ticker(ticker):
        raise ValuateError(
            400,
            {
                "type": "INSUFFICIENT_DATA",
                "ticker": ticker,
                "reason": "ticker must contain only letters, digits, '.', and '-' characters",
            },
        )
    return normalize_ticker(ticker)


def _load_fundamentals_or_raise(ticker: str, source_name: str) -> CompanyFundamentals:
    try:
        return load_fundamentals(
            ticker, source_name, Period.ANNUAL, config.DEFAULT_RANGE
        )
    except TickerNotFound as exc:
        raise ValuateError(404, {"type": "NOT_FOUND", "ticker": ticker}) from exc
    except (SourceUnavailable, MissingCredentials, UnsupportedPeriod, KeyError) as exc:
        raise ValuateError(
            502,
            {
                "type": "API_ERROR",
                "ticker": ticker,
                "endpoint": source_name,
                "message": str(exc),
            },
        ) from exc


def _fetch_consensus_best_effort(ticker: str) -> AnalystConsensus | None:
    # fetch_analyst_consensus already degrades every internal failure to None
    # (see its own docstring); this call is not wrapped further, matching the
    # original's "must never take down a valuation that only needed the
    # primary data source" contract for the Yahoo lookup.
    return fetch_analyst_consensus(ticker)


def _current_price_or_raise(fundamentals: CompanyFundamentals, ticker: str) -> float:
    price_series = fundamentals.series.get("price")
    if price_series is None or not price_series.available or not price_series.points:
        raise ValuateError(
            400,
            {
                "type": "INSUFFICIENT_DATA",
                "ticker": ticker,
                "reason": "unable to resolve a current price",
            },
        )
    latest = max(price_series.points, key=lambda point: point.date)
    return (
        latest.value.as_base_units()
        if isinstance(latest.value, Money)
        else latest.value
    )


def _as_optional_number(value: Any) -> float | None:
    return value if isinstance(value, (int, float)) else None


def _or_default(value: Any, default: float) -> Any:
    """Matches JS's `??` (nullish coalescing): substitutes `default` only for a
    missing/non-numeric value, never for an explicit `0` -- unlike Python's
    `or`, which would treat `0` as falsy and silently replace it. A request
    with e.g. `bearExitPeMultiple: 0` must reach `calculate_rule_one_value` as
    `0` (so it produces the typed `INVALID_EXIT_PE` result), not be silently
    rewritten to the default `10` first."""
    return value if isinstance(value, (int, float)) else default


def _scenario_growth(
    explicit: Any, effective_growth: float | None, *, bear: bool
) -> float | None:
    """Bear/bull growth: the user's own explicit value if provided, else
    derived from the base scenario (x0.75/-3 for bear, x1.25/+3 for bull) --
    only when the request omits the field entirely, matching the original's
    "older client" fallback exactly."""
    if isinstance(explicit, (int, float)):
        return explicit
    if effective_growth is None:
        return None
    if bear:
        derived = (
            effective_growth * 0.75 if effective_growth > 0 else effective_growth - 3
        )
    else:
        derived = (
            effective_growth * 1.25 if effective_growth > 0 else effective_growth + 3
        )
    return round(derived, 2)


def _serialize_data(
    fundamentals: CompanyFundamentals, resolved: ResolvedEps, current_price: float
) -> dict[str, Any]:
    historical_pe = compute_historical_pe_averages(fundamentals)
    return {
        "ticker": fundamentals.ticker,
        "currentPrice": current_price,
        "currency": fundamentals.currency.value,
        "epsTtm": resolved.template_eps_ttm,
        "asOf": datetime.now(UTC).isoformat(),
        "staleTtmWarning": resolved.source != "twelvedata",
        "growth": {
            "historical1yPercent": historical_1y_growth_percent(fundamentals),
            "historical3yPercent": historical_3y_growth_percent(fundamentals),
            "historical5yPercent": historical_5y_growth_percent(fundamentals),
            "analystEstimate5yPercent": None,  # no source in this merge, see growth.py
            "epsTtmGrowthPercent": calculate_ttm_eps_growth_percent(fundamentals),
        },
        "historicalPe": {
            "avg1y": historical_pe.avg_1y,
            "avg3y": historical_pe.avg_3y,
            "avg5y": historical_pe.avg_5y,
        },
    }


def _serialize_result(result: ValuationOk | ValuationErr) -> dict[str, Any]:
    if not result.ok:
        return {"ok": False, "error": result.error}
    body: dict[str, Any] = {
        "ok": True,
        "fairValue": result.fair_value,
        "inputs": {
            "epsTtm": result.inputs.eps_ttm,
            "growthRatePercentRaw": result.inputs.growth_rate_percent_raw,
            "growthRatePercentClamped": result.inputs.growth_rate_percent_clamped,
        },
    }
    if isinstance(result.inputs, RuleOneInputsUsed):
        body["inputs"].update(
            {
                "exitPeMultiple": result.inputs.exit_pe_multiple,
                "requiredReturnPercent": result.inputs.required_return_percent,
                "years": result.inputs.years,
                "mosPercent": result.inputs.mos_percent,
            }
        )
    if result.intermediate:
        body["intermediate"] = {
            "epsFuture": result.intermediate.get("eps_future"),
            "futurePrice": result.intermediate.get("future_price"),
            "stickerPrice": result.intermediate.get("sticker_price"),
            "mosPrice": result.intermediate.get("mos_price"),
        }
    return body


def _serialize_consensus(consensus: AnalystConsensus | None) -> dict[str, Any] | None:
    if consensus is None:
        return None
    return {
        "ticker": consensus.ticker,
        "nextYearEpsGrowthPercent": consensus.next_year_eps_growth_percent,
        "priceTarget": {
            "mean": consensus.price_target.mean,
            "high": consensus.price_target.high,
            "low": consensus.price_target.low,
            "numberOfAnalysts": consensus.price_target.number_of_analysts,
        },
        "recommendationKey": consensus.recommendation_key,
        "beta": consensus.beta,
        "priceToSales": consensus.price_to_sales,
        "ruleOf40": consensus.rule_of_40,
        "trailingEps": consensus.trailing_eps,
        "mostRecentQuarterEndDate": (
            consensus.most_recent_quarter_end_date.isoformat()
            if consensus.most_recent_quarter_end_date
            else None
        ),
        "asOf": consensus.as_of.isoformat(),
    }
