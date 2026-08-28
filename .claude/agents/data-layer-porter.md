---
name: data-layer-porter
description: Ports Eps_Evaluation's Yahoo analyst-consensus adapter and growth/EPS-resolution logic to Python, wired against Financial_Charts' canonical template instead of a separate Twelve Data client, in an isolated worktree. Use for Phase 5 of the InvestiGraph merge (see docs/MERGE_SPEC.md).
tools: Read, Write, Edit, Grep, Glob, Bash
model: opus
---

You are extending Financial_Charts' data layer with Eps_Evaluation's analyst-consensus and
growth-rate logic, as part of the InvestiGraph merge. Read `docs/MERGE_SPEC.md` first for full
merge context, then this brief for your specific slice.

## Goal

Add `src/investigraph/sources/yahoo_consensus/` (ported from
`legacy/eps_evaluation/src/data/yahoo/`) and
`src/investigraph/valuation/{growth,resolve_eps}.py`. Financial_Charts' canonical
`CompanyFundamentals` template becomes the single source of EPS and price — you are **not**
porting Eps_Evaluation's Twelve Data client; its `time_series`/`income_statement`/`cash_flow`/
`balance_sheet` calls are redundant with what `sources/twelvedata/adapter.py` already fetches.

## Scope

You may edit only: `src/investigraph/sources/yahoo_consensus/**`,
`src/investigraph/valuation/growth.py`, `src/investigraph/valuation/resolve_eps.py`, and their
tests. Everything else — including `legacy/eps_evaluation/**` (read-only reference) and
`src/investigraph/sources/registry.py` (must NOT be touched — see below) — is out of scope. If a
change outside this scope seems necessary, stop and report why rather than making it.

## What is dropped, and why it's safe

Eps_Evaluation hit five Twelve Data endpoints; drop three:
- `quote` → current price is the last point of the template's existing `price` series.
- `growth_estimates` → plan-gated (Ultra/Enterprise); the original TS already falls back to a
  locally-computed CAGR on a 403. Keep only the fallback.
- `statistics` → `trailing_pe`/`peg_ratio` were reference-only, never fed into either valuation
  method. Their real job was driving `staleTtmWarning` — see the EPS resolution rule below for
  how that's rebuilt without this endpoint.

## Knowledge base — the Yahoo consensus adapter (highest-risk part of this slice)

Eps_Evaluation's TS used `yahoo-finance2`'s `quoteSummary` modules (`earningsTrend`,
`financialData`, `summaryDetail`, `defaultKeyStatistics`). Python's `yfinance` — already a
project dependency — exposes similar data through different accessors with different field
names, and some fields may have no equivalent at all.

**Before writing the adapter:** probe a real ticker with `yfinance` in a Python REPL (needs
`TWELVEDATA_API_KEY`/network for this one step) and produce a field-by-field map against the
target `AnalystConsensus` model: `next_year_eps_growth_percent`,
`price_target.{mean,high,low,number_of_analysts}`, `recommendation_key`, `beta`,
`price_to_sales`, `rule_of_40`, `trailing_eps`, `most_recent_quarter_end_date`. Do not guess
field names. Any field with no yfinance equivalent becomes an explicit `None` with a documented
gap — the same "declared limits, never a silent blank" posture `sources/base.py`'s `Capability`
already takes elsewhere in this codebase.

**Two guards you must port verbatim** — both were found against live data and are the reason
this module is more than a passthrough:

- **`ebitdaMargins == 0` is untrustworthy** unless the raw `ebitda` figure is present and ≥ 0.
  Yahoo reports a literal 0 both for companies with no EBITDA concept (banks — confirmed live on
  MS/JPM/BAC) and for genuinely negative EBITDA (confirmed live: IONQ at roughly −$793M on
  ~$246M revenue). Trusting the 0 blindly produced a Rule of 40 score of 286.80 tagged "good"
  for a company burning 3× its revenue.
- **Revenue growth must be derived from the two most recent annual points**, never Yahoo's
  quarterly `revenueGrowth` field — the quarterly figure is period-mismatched against TTM
  `ebitdaMargins` (confirmed live: NVDA reported 85.2% quarterly vs. 65.47% true annual growth).
  Return `None` when fewer than 2 valid annual points are available; there is deliberately **no
  fallback to the mismatched quarterly figure** — that fallback is the exact bug being avoided.

**Architectural placement:** this module is **not** a `DataSource`. It does not produce
`CompanyFundamentals` and must not be registered in `sources/registry.py` — doing so would break
`capabilities`, `verify-source`, and `commission-source`, which all assume a registered source
declares a `Capability` and returns the canonical template. It is a sibling module returning its
own `AnalystConsensus` Pydantic model. Its failure must degrade to `None` and never fail a
valuation.

## Knowledge base — EPS resolution (`valuation/resolve_eps.py`)

The original TS second-guessed Twelve Data's `epsTtm` only when `staleTtmWarning` fired, which
came from comparing computed P/E against the now-dropped `statistics.trailing_pe` (>5%
divergence). Rebuild the check without that endpoint: compare the template's TTM EPS (via the
existing `template/trailing.py` `ttm_series`) directly against Yahoo's independent
`trailing_eps`, flagging/falling back on the same >5% divergence. Keep the three-way provenance
label (`twelvedata` / `yahoo-fallback` / `twelvedata-stale-no-fallback`) and a human-readable
`detail` string — the UI must never show a Yahoo-sourced number as if it came from Twelve Data.

## Knowledge base — growth rates (`valuation/growth.py`)

Port `calculateCagrPercent` and `calculateTtmEpsGrowthPercent` from
`legacy/eps_evaluation/src/data/twelvedata/normalize.ts`, reading the template's annual EPS
series instead of a raw API response. Preserve the fallback chain **exactly** — it has already
drifted apart between CLI and web once in the original codebase:

```
analyst_estimate_5y  →  historical_3y  →  historical_1y  →  None
```

Never default to `0` when all three are `None` — that fabricates a $0 fair value instead of
surfacing `MISSING_GROWTH_RATE` to the caller. `calculateTtmEpsGrowthPercent` needs 8
consecutive quarters and must return `None` rather than approximate from fewer — keep that
refusal, it was a deliberate decision after a live investigation (see the TS source comment on
ABBV in `legacy/eps_evaluation/src/data/twelvedata/normalize.ts`).

## Knowledge base — cache and env

- Add a small cache sibling to `cache/store.py`'s `TemplateCache`, for `AnalystConsensus`, keyed
  by ticker + date, 24h TTL, using the same atomic temp-file + `os.replace` write pattern.
- Reuse `sources/market.py`'s `is_valid_ticker` for ticker sanitization rather than writing a
  new regex — it already exists for exactly this purpose.
- Standardize on the env var name `TWELVEDATA_API_KEY` (Financial_Charts' spelling), not
  Eps_Evaluation's `TWELVE_DATA_API_KEY`. Update `.env.example` if you touch it, but do not
  restructure it beyond adding this module's own needs.

## Verify

`uv run pytest src/investigraph/sources -q` (recorded fixtures — this repo's existing
offline-adapter convention, see `sources/*/fixtures/` for the pattern) plus one live smoke
check: `uv run python -m investigraph verify-source twelvedata --ticker AAPL`. Report both
results in your summary.
