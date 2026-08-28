from __future__ import annotations

from pydantic import BaseModel


class ScenarioValuation(BaseModel):
    """One Bear/Base/Bull scenario's assumptions and computed fair values.

    Ported from legacy/eps_evaluation/src/history/types.ts's `ScenarioValuation`.
    """

    growth_rate_percent: float | None = None
    exit_pe_multiple: float | None = None
    required_return_percent: float | None = None
    mos_percent: float | None = None
    lynch_fair_value: float | None = None
    rule_one_fair_value: float | None = None


class SavedValuation(BaseModel):
    """A saved EPS valuation record.

    Ported from legacy/eps_evaluation/src/history/types.ts's `SavedValuation`. Carries
    both the legacy flat fields (`growth_rate_percent`, `exit_pe_multiple`,
    `required_return_percent`, `mos_percent`, `lynch_fair_value`,
    `rule_one_fair_value`) written by the original CLI's `--save`, and the newer
    nested `base`/`bear`/`bull` scenario fields written by the web UI's 3-scenario
    save. A single record only ever populates one shape or the other, never both --
    but both must round-trip through this one model rather than a discriminated
    union: the original TS deliberately tolerated mixed old/new records, and a
    discriminated union would reject them.

    Every field except `ticker` is optional. This mirrors the original's actual
    runtime contract exactly: TypeScript interfaces aren't checked at runtime, and
    `readHistoryFile`'s malformed-entry filter (see `store.read_history_file`) only
    ever verified that a raw JSON entry was an object with a string `ticker` field --
    a hand-edited history.json missing any other field (e.g. `currentPrice`) was
    tolerated, not rejected. Keeping every other field optional here preserves that
    laxity instead of silently turning old/partial records into dropped rows.
    """

    ticker: str
    id: str | None = None
    evaluated_at: str | None = None  # ISO 8601, e.g. "2026-08-19T18:45:00.000Z"
    current_price: float | None = None
    currency: str | None = None
    eps_ttm: float | None = None
    eps_override: float | None = None
    years: float | None = None

    # Legacy flat fields (optional, for backward compatibility).
    growth_rate_percent: float | None = None
    exit_pe_multiple: float | None = None
    required_return_percent: float | None = None
    mos_percent: float | None = None
    lynch_fair_value: float | None = None
    rule_one_fair_value: float | None = None

    # Newer nested per-scenario fields.
    base: ScenarioValuation | None = None
    bear: ScenarioValuation | None = None
    bull: ScenarioValuation | None = None

    notes: str | None = None
    evaluator: str | None = None


class InvalidHistoryInput(Exception):
    """Raised by `save_valuation`/`delete_valuation` on a basic input sanity failure.

    E.g. a blank ticker on save, or a blank id on delete. Mirrors the original's
    `HistoryError` of type `INVALID_INPUT`, adapted to this codebase's convention of
    raising typed exceptions rather than returning a `{ ok, error }` result (see
    `investigraph.sources.base`'s `TickerNotFound`/`SourceUnavailable`/etc.).
    """


class ValuationNotFound(Exception):
    """Raised by `delete_valuation` when no record with the given id exists.

    Mirrors the original's `HistoryError` of type `NOT_FOUND`.
    """
