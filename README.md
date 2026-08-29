# InvestiGraph

A Python tool for **US and Tel Aviv Stock Exchange (TASE)** tickers that renders a fixed grid of
fundamentals charts *and* a Rule #1 fair-value panel (Bear/Base/Bull scenarios) from a
single ticker lookup — one dashboard per company, chart grid and valuation side by side.

Use it two ways: a **CLI** for a static export, or a **local web UI** where you type a ticker
once and both halves render together.

InvestiGraph is a merge of two previously separate tools — [Financial_Charts](docs/financial_charts_progress.md)
(the chart grid) and Eps_Evaluation (the valuation engine, ported from TypeScript) — see
[docs/MERGE_SPEC.md](docs/MERGE_SPEC.md) for the full merge plan and rationale, and
[PROGRESS.md](PROGRESS.md) for phase-by-phase status.

## Quick start

Requires **Python 3.12+** and [uv](https://docs.astral.sh/uv/). The web UI additionally needs
network access to `cdn.plot.ly` (chart rendering) and `cdn.jsdelivr.net` (the valuations
dashboard's Chart.js) at page load.

```sh
uv sync                                          # install dependencies
uv run python -m investigraph.web --port 8000    # web UI → open the (forwarded) port
uv run python -m investigraph AAPL --out out/AAPL.html   # CLI → static chart page
```

Copy [.env.example](.env.example) to `.env` and fill it in (`.env` is never committed):

```sh
DATA_SOURCE=yfinance        # or twelvedata; overridable per render with --source
TWELVEDATA_API_KEY=         # only required when DATA_SOURCE=twelvedata
```

`yfinance` needs no key. The Yahoo analyst-consensus data used by the valuation panel (growth
estimates, price targets) also needs no key — it's a separate public endpoint.

## Usage

### Web UI — chart grid + fair-value panel together

```sh
uv run python -m investigraph.web --host 0.0.0.0 --port 8000
```

Enter a ticker once: the chart grid (Plotly.js, interactive) and the Bear/Base/Bull fair-value
cards render from the same fetch. Save a valuation with an evaluator name and it shows up on
`/static/valuations.html`, a sortable "all valuations" dashboard with live prices and an
upside-% chart. Key endpoints: `GET /chart-data`, `POST /api/valuate`, `GET/POST /api/history`,
`DELETE /api/history/<id>`, `GET /api/valuations`, `GET /api/live-prices`. Also served: `GET /`
(the ticker/chart-set picker page itself), `GET /render` (a server-rendered HTML dashboard; no
front-end code calls this anymore — the picker page above fetches `/chart-data` and renders
client-side instead, so this route is currently unused by the shipped UI), and `POST /chart-sets`
(saves a custom chart set from the checkbox picker for reuse).

### CLI — render a static dashboard

```sh
# US via the free source
uv run python -m investigraph AAPL --source yfinance --period annual --range 10y --out out/AAPL.html
# TASE via the paid source (native ₪, agorot/millions handled — see CLAUDE.md's Gotchas)
uv run python -m investigraph TEVA.TA --source twelvedata --range 10y --out out/TEVA.html
```

`TICKER [--source] [--period quarterly|ttm|annual] [--range 6m|1y|3y|5y|10y|max] [--chart-set]
[--charts price,eps,margins] [--out PATH]`. `--out` accepts `.html`, `.png`, or `.pdf`; it
defaults to `out/<TICKER>.html`. **`--period ttm` is derived, not natively fetched from either
source** — Twelve Data has no TTM endpoint at all, and yfinance's native TTM statements exist
but only cover income statement / cash flow, not the balance sheet, and can disagree with a
plain 4-quarter sum after a restatement; deriving both sources' TTM the same way keeps behavior
uniform and avoids that surprise. Both adapters fetch `Period.QUARTERLY` and sum each flow
metric (revenue, net income, EPS, FCF, EBITDA, …) themselves (`template/trailing.py`'s
`derive_ttm_fundamentals`); balance-sheet metrics and price pass through as their full quarterly
series unchanged, since summing snapshot values would be meaningless. `gross_margin` is the one
exception: it can't be correctly recomputed for TTM (its numerator isn't tracked as its own
series), so its whole quarterly series passes through as a labeled approximation instead — every
point is that quarter's own margin, not a trailing figure — flagged in the page's source-limits
panel; `net_margin` *is* correctly recomputed (both its inputs are available as flow series). A
TTM window missing a quarter (a gap in the underlying quarterly data) breaks the plotted line at
that point rather than silently interpolating across it — the same convention every other
computed metric in `template/` uses for a bad or missing point. The
default `fundamentals` chart set renders 6 charts; the catalog holds 21 — use `--charts`
(comma-separated ids) or the web UI's checkbox picker for any other combination. Tickers are
matched by `^[A-Za-z0-9.\-]+$` — no exchange-qualified form like `AAPL:NASDAQ`; use the bare
symbol (`.TA` routes to TASE).

### CLI — `valuate`: the same fair-value engine, from the command line

```sh
uv run python -m investigraph valuate AAPL
```

`valuate TICKER [-s|--save] [-m|--mos PERCENT] [-n|--notes TEXT] [-H|--history]` — `--save`
persists the result to history; `--mos` sets the Rule #1 Margin of Safety percent (e.g. `25` for
25%, default `0`); `--notes` attaches free text to a saved record; `--history` lists saved
valuations instead of computing a new one (optionally filtered to `TICKER` if given). Uses fixed
Rule #1 assumptions — exit P/E multiple 15, 15% required return, a 10-year horizon — matching the
original TS CLI's constants; these aren't currently configurable from the CLI.

Calls the exact same growth-fallback chain and valuation math the web UI's `/api/valuate` uses,
so a CLI figure and a web figure for identical inputs always match (see CLAUDE.md's Gotchas on
why that's a named invariant, not an accident).

### Developer commands

- `verify-source <name> --ticker <sample>` — live-reconciles a source's declared `Capability`
  against what it actually returns. Never run during a normal render.
- `capabilities [<name>] [--matrix]` — offline, prints a registered source's declared metrics/
  markets/periods/history depth.
- `commission-source <name>` — probes a source live and regenerates its `capability.py`; review
  the diff before committing (see
  [docs/financial_charts_progress.md](docs/financial_charts_progress.md) for a caveat on metric
  coverage — its probe is scoped to metrics with a consuming chart, so it can drop a
  not-yet-charted metric from the regenerated declaration).

## Architecture

Data flows one way — **env-configured data source → per-source adapter → canonical template →
display** — and the display layer (charts *and* valuation) reads only the template, never a
data source directly.

- **Pluggable data sources.** `yfinance` (free) and `twelvedata` (paid), chosen by `DATA_SOURCE`.
  Adding a source = an adapter + a declared `Capability` + a registry entry.
- **Canonical template** (`template/models.py`, Pydantic): every monetary series is a
  `Money`-style `(value, currency, scale)` value, so a TASE ticker's agorot-priced shares and
  shekel-millions financials can never be silently combined.
- **Valuation** (`valuation/`): pure functions ported from Eps_Evaluation's TS — Rule #1-style
  fair value, a single shared growth-rate fallback chain
  (`analyst_estimate_5y → historical_3y → historical_1y → None`) used by both the CLI and the
  web UI so they can't drift apart.
- **History** (`history/`): disk-backed saved-valuation store, per-evaluator files, ported from
  Eps_Evaluation's TS store. Storage location is overridable via the optional
  `HISTORY_FILE_PATH` env var (see [.env.example](.env.example)) — it takes precedence over
  per-evaluator storage when set.
- **Markets: US + TASE, native currency only** (₪ / $, no FX conversion), routed by the `.TA`
  suffix.
- **Caching:** one on-disk cache directory (`.cache/`) serves both charts and valuation data.

Full architectural detail, decisions, and gotchas live in [CLAUDE.md](CLAUDE.md).

## Status

See [PROGRESS.md](PROGRESS.md) for the merge's phase-by-phase history and
[docs/financial_charts_progress.md](docs/financial_charts_progress.md) for the chart engine's
own pre-merge build log.

## Development

```sh
uv sync              # install/lock dependencies
scripts/test.sh       # full suite: pytest (Python) + vitest (front-end jsdom tests)
uv run ruff check    # lint
uv run ruff format   # format
```

Conventions (simplicity, modularity, verification policy, workflow) live in
[CLAUDE.md](CLAUDE.md). The `.claude/` hooks auto-format/lint edited files and gate turns on a
green test suite.
