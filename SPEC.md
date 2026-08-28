# SPEC: Financial Charts — Company Fundamentals Dashboard (v1)

> Self-contained spec. Implement in a **fresh session**, task by task, then run the
> Verification section. Conventions live in [CLAUDE.md](CLAUDE.md).

## 1. Goal

Give an investor a one-look evaluation of a company's fundamentals. Enter a ticker; the tool
fetches that company's financials and **renders a fixed grid of fundamental charts, all at
once, as a static page**. It must work for both **US** and **Tel Aviv Stock Exchange (TASE)**
listings, from either a free source (yfinance) or a paid source (Twelve Data), chosen by
environment configuration — without the chart layer knowing or caring which source produced
the data.

Success: `python -m financial_charts AAPL` (US) and `python -m financial_charts TEVA.TA`
(TASE) each produce a static dashboard page whose charts are correct, correctly-labelled in
native currency, and degrade gracefully to "No Data" where a source lacks a metric.

## 2. Scope

**In scope (v1):**
- Two data-source adapters behind one interface: **yfinance** (free) and **Twelve Data**
  (paid), selected via env config (`DATA_SOURCE`).
- Both markets: **US** and **TASE**, routed by ticker **`.TA` suffix** (bare = US).
- **Native currency only** — USD for US, ILS (₪) for TASE. No FX conversion.
- Canonical **Pydantic template** as the single display data model, with a `Money` type
  carrying value + currency + scale/unit.
- **Per-source capability declaration + validation** that surfaces each source's limits
  (metrics available, history depth, markets, periods) to the user.
- **Disk caching** of the fetched template.
- An **extensible chart module**: a core set of built-in charts plus a registry so a
  developer can define **custom chart sets**. The dashboard renders a named chart set.
- **Static output**: a single HTML page (grid of chart cards) with optional PNG/PDF export.
- **Configurable-per-render** period (Quarterly / TTM / Annual) and time range
  (6M / 1Y / 3Y / 5Y / 10Y / max), via CLI/config with sensible defaults. **Status:** `TTM`
  is modeled in `Period` but no adapter has declared support for it yet — a request for it
  is rejected pre-fetch by `require_supported_period` with a clear error, same as any other
  declared gap, rather than silently mismapped.

**Out of scope (v1):**
- Interactive UI for the CLI's static PNG/HTML/PDF export — that output stays static
  matplotlib. **Status:** the browser dashboard (`web/`) is exempt from this — its charts are
  interactive (hover, zoom, legend toggle) via a client-side JS chart library reading the
  template's existing JSON serialization; see PROGRESS.md.
- FX / cross-currency comparison.
- Multi-company comparison, watchlists, news/"brief" panels, alerts.
- Sources other than yfinance and Twelve Data.
- Publishing/hosting the output anywhere.

## 3. Design

### Data flow (one way)
```
CLI/config → source registry picks adapter (by DATA_SOURCE)
          → adapter fetches + normalizes → canonical template (Pydantic, cached to disk)
          → chart set (built-in + custom) reads ONLY the template
          → dashboard renders the grid → static HTML/PNG/PDF
```
The display layer never imports a source; adapters never import charts. The template is the
only shared contract.

### Module layout (vertical slices; tests colocated as `*_test.py`)
```
financial_charts/
  __main__.py          # CLI: TICKER [--source] [--period] [--range] [--chart-set] [--charts] [--out]; subcommands: render, verify-source, capabilities, commission-source
  config.py            # env config: DATA_SOURCE + render defaults; loads .env (each adapter reads its own credentials)
  chart_support.py     # which catalog charts a source's declared metrics can actually feed
  template/
    models.py          # Money, Currency, Unit, Period; Point, Series, MetricSeries; CompanyFundamentals (THE template)
    derived.py         # metrics computed from base series (margins, ratios, ROIC/ROCE, …), not fetched
    models_test.py derived_test.py
  sources/
    base.py            # DataSource Protocol + Capability model (published interface)
    validation.py      # RENDER-TIME: declared Capability vs a requested (market, period, range) → source_limits
    verify.py          # DEV-TIME: reconcile declared Capability vs a LIVE fetch → mismatch report (used by verify-source)
    commission.py      # DEV-TIME: probe a source live across sample tickers → generated capability.py (commission-source)
    registry.py        # DATA_SOURCE env value → adapter instance
    market.py          # ticker → Market (US | TASE) via `.TA` suffix
    ranges.py          # the shared --range vocabulary + its range → years table
    currency.py        # source currency code → template Currency (incl. the agorot "ILA" rule)
    yfinance/
      adapter.py capability.py adapter_test.py
    twelvedata/
      adapter.py capability.py adapter_test.py
  cache/
    store.py store_test.py   # get/put template keyed by (ticker, source, period, range, date)
  charts/
    base.py            # Chart interface: name, title, required metrics, render(ax, template)
    catalog.py         # every registered chart, by id — what --charts and the web picker choose from
    registry.py        # register charts + named chart SETS (built-in "fundamentals" set + custom)
    builtins/          # price.py revenue.py net_income.py free_cash_flow.py eps.py margins.py (+ more added incrementally)
    <chart>_test.py
  dashboard/
    layout.py          # select chart set → render each chart (matplotlib) → grid
    render.py          # compose grid into a static HTML page (Jinja2) + optional PNG/PDF export
    layout_test.py
  web/                 # independent browser UI (Flask); composes published interfaces only
    __main__.py app.py # dev server entry point + routes: / , /render , /chart-data , /chart-sets
    service.py         # ticker → template, shared by the routes
    chart_data.py      # template + chart set → JSON for the client-side Plotly charts
    chart_set_store.py # disk persistence for user-created chart sets
    templates/         # index.html (the dashboard page)
```

### Key interfaces

**`sources/base.py`**
- `Capability` (Pydantic): `markets: set[Market]`, `periods: set[Period]`,
  `max_history: dict[Period, int]` (e.g. `{ANNUAL: 10}`), `metrics: set[str]` (canonical
  metric ids it can supply). Declared statically per source in its `capability.py`.
- `DataSource` (Protocol): `capability() -> Capability` and
  `fetch(ticker: str, market: Market, period: Period, range: Range) -> CompanyFundamentals`.
  Adapters raise `TickerNotFound`, `SourceUnavailable`, `MissingCredentials` (defined here).
  A fourth error, `UnsupportedPeriod`, is also defined here and raised pre-fetch by
  `validation.require_supported_period` — it is the one a user actually hits today, via
  `--period ttm`.

**Two separate capability checks — do not conflate:**
- `sources/validation.py` (**render time**): given a declared `Capability` + a requested
  `(market, period, range)`, returns the unmet requests that become `source_limits` on the page.
  Pure, offline, deterministic — the normal render path uses only this and **never probes live**.
- `sources/verify.py` (**dev time**): `reconcile(adapter, sample_ticker, ...)` does a **live**
  fetch and compares the actual response to the declared `Capability`, returning a report of
  declared-but-missing metrics, undeclared extras, unit/currency/scale surprises, and actual-vs-
  declared history depth. Invoked only by the `verify-source` CLI subcommand, never on render.

**`template/models.py`** — canonical model every adapter fills and every chart reads:
- `Money(value: float, currency: Currency, scale: Unit)` — `Currency ∈ {USD, ILS}`,
  `scale ∈ {ONES, THOUSANDS, MILLIONS, ...}`. Provides `.to(scale)` for safe rescaling.
  Charts format via `Money`, so agorot-vs-millions can never be mixed by accident.
- `MetricSeries(metric_id, points: list[Point(date, value: Money | float)], available: bool)`.
- `CompanyFundamentals(ticker, market, currency, period, range, series: dict[str, MetricSeries], source_limits: list[str])`
  — `source_limits` carries the human-readable capability gaps to show on the page.

**`charts/base.py`** — `Chart` declares `required_metrics`; if the template marks any as
unavailable, the chart renders a "No Data" card instead of failing. `registry.py` holds the
built-in `"fundamentals"` chart set and lets a developer register additional named sets.

### TASE specifics (must be handled in the TASE branch of each adapter)
- Prices quoted in **agorot (1/100 ₪)** → convert to ILS in the `Money`. Financial-statement
  figures in **millions of shekels** → stored as `Money(scale=MILLIONS, currency=ILS)`.
- Twelve Data: map `.TA` → its exchange/`mic_code` (Tel Aviv, MIC `XTAE`); confirm each
  metric's returned unit and normalize. yfinance: use the `.TA` symbol directly.

### Introducing a new data source (config-as-code + explicit verify)

A new source is added by declaration, then confirmed by an explicit command — the app never
probes silently:

1. Create `sources/<name>/adapter.py` implementing the `DataSource` Protocol.
2. Create `sources/<name>/capability.py` — a declared `Capability` (markets, periods, metrics,
   `max_history`, unit/currency notes). This is the config-as-code contract.
3. Register it in `sources/registry.py` so `DATA_SOURCE=<name>` resolves to it.
4. Add secrets to `.env` (e.g. `<NAME>_API_KEY`).
5. Run `verify-source` (below) to reconcile the declaration against the live API; fix
   `capability.py` until the report is clean, and pass `--write-fixture` to record fixtures for
   the offline unit tests.
6. Commit adapter + capability + fixtures + tests.

**`verify-source` command** (subcommand of `__main__.py`, backed by `sources/verify.py`):
```sh
python -m financial_charts verify-source <name> --ticker <sample> \
    [--market US|TASE] [--period ...] [--range ...] [--write-fixture]
```
Instantiates the adapter, fetches the sample ticker **live**, and prints a reconciliation report:
declared-but-missing metrics (**mismatch**), undeclared extras (**info**), unit/currency/scale
sanity checks incl. TASE agorot-vs-millions (**warning**), and actual-vs-declared history depth.
**Exits non-zero on any mismatch** so it can gate CI. It is a deliberate developer action, run at
onboarding or when a source changes — not part of any render.

### Dependencies to add (via `uv add`)
`pydantic`, `yfinance`, `twelvedata` (or `requests` for its REST API), `matplotlib`,
`jinja2`, `python-dotenv`, `flask` (the `web/` dev server). Dev: `pytest`, `ruff` (also wire
the three `.claude/hooks`).

Plotly.js — the browser dashboard's chart library — is **not a Python package**: it is loaded
from `cdn.plot.ly` by `web/templates/index.html`, pinned to an exact version, so it will never
appear in `pyproject.toml`. The trade-off is that the browser UI needs network access to that
CDN at page load; the CLI does not.

## 4. Tasks (in implementation order; each small and verifiable)

1. Install toolchain & scaffold: `uv init`, add deps above, create the package tree and empty
   slices; `uv sync` succeeds.
2. `template/models.py`: implement `Money` (+ `.to()` rescaling), `Currency`, `Unit`,
   `Period`, `Point`, `MetricSeries`, `CompanyFundamentals`. Tests: `Money` rescaling and a
   guard that two `Money` of different currency/scale never silently add.
3. `sources/market.py`: `market_of(ticker)` — `.TA` → TASE, else US. Test both.
4. `sources/base.py`: `Capability`, `DataSource` Protocol, error types.
5. `sources/validation.py`: given a `Capability` + a requested (market, period, range),
   return the list of limits/unmet requests (feeds `source_limits`). Test the 4y-vs-10y case.
6. `sources/yfinance/`: `capability.py` + `adapter.py` mapping yfinance data → template. Test
   with a recorded fixture (no live network in tests). **Decided while implementing:** the
   declaration grants the same metrics to US and TASE rather than the originally-sketched "US
   strong, TASE prices only / sparse fundamentals". `Capability` has one flat `metrics` set
   and one flat `markets` set — per-market metrics aren't expressible without changing the
   model — and yfinance's TASE sparseness is *per ticker*, not per market, so a market-level
   narrowing would be wrong in both directions. Sparseness is therefore handled one level
   down, by the adapter's per-metric `available` flag, which degrades an individual chart to
   "No Data". `capability.py` says what the source can supply in general; it is not a
   per-ticker guarantee.
7. `cache/store.py`: disk get/put of `CompanyFundamentals` (JSON) keyed by
   `(ticker, source, period, range, date)`; cache-first read. Test round-trip + key.
8. `sources/twelvedata/`: `capability.py` + `adapter.py` (US + TASE via exchange mapping,
   agorot/millions normalization). Test with recorded fixtures for one US and one TASE ticker.
9. `sources/verify.py` + the `verify-source` CLI subcommand: reconcile a declared `Capability`
   against a live fetch; report mismatches/extras/unit-warnings and exit non-zero on mismatch.
   `--write-fixture` records the raw response — **use it to generate the adapter test fixtures**
   for tasks 6 and 8. Test the reconciliation logic with a stubbed adapter (no live network).
10. `sources/registry.py` + `config.py`: `DATA_SOURCE` env → adapter; load `.env`; missing
    paid credentials raise `MissingCredentials` with a clear message.
11. `charts/base.py` + `charts/registry.py`: `Chart` interface, "No Data" fallback, and the
    named-chart-set registry with a built-in `"fundamentals"` set.
12. `charts/builtins/`: core charts — Price (+ SMA 50/150/200), Revenue, Net Income,
    Free Cash Flow, EPS, Margins. One slice + test each.
13. `dashboard/layout.py` + `render.py`: render the selected set into a matplotlib grid and a
    static HTML page (Jinja2 card grid); show `source_limits`; optional `--out` PNG/PDF.
14. `__main__.py`: wire the render CLI (`TICKER [--source] [--period] [--range] [--chart-set]
    [--out]`) and the `verify-source` subcommand end-to-end.
15. Wire `.claude/hooks` now that the toolchain exists — venv-absolute so they don't depend on
    an activated shell: `FORMAT_CMD="$CLAUDE_PROJECT_DIR/.venv/bin/ruff format"`,
    `LINT_CMD="$CLAUDE_PROJECT_DIR/.venv/bin/ruff check"`,
    `TEST_CMD="$CLAUDE_PROJECT_DIR/.venv/bin/pytest -q"`.
16. Add remaining inventory charts incrementally as their own slices: EBITDA, Cash & Debt,
    Dividends, Return of Capital (ROIC/ROCE), Shares Outstanding, Ratios, Valuation (P/B),
    Expenses, Assets/Equity/Liabilities, Debt & Financial Leverage, plus KPI cards.

## 5. Edge cases & errors

- **Unknown/invalid ticker** → `TickerNotFound`; CLI prints a clear message, no page written.
- **Source lacks a metric/period** (declared in `Capability`) → that chart renders a
  "No Data" card; the gap is listed in `source_limits` on the page. Never a crash, never a
  silent blank.
- **History shorter than requested range** (free tier = 4y vs requested 10y) → render what
  exists; note the limit in `source_limits`.
- **Network / API failure** → if a valid cache entry exists, use it and mark the page stale;
  otherwise `SourceUnavailable` with a clear message.
- **Missing paid credentials** (`DATA_SOURCE=twelvedata`, no key) → `MissingCredentials`
  naming the env var; do not fall back silently to a different source.
- **Twelve Data rate limits / credits** → cache-first minimizes calls; on limit, back off and
  surface a clear message.
- **TASE units** → prices in agorot converted to ILS; statements in millions-of-shekels kept
  as `Money(MILLIONS, ILS)`; a unit test asserts a known agorot price → correct ₪ value.
- **Custom chart requires an unavailable metric** → same "No Data" fallback.
- **New/changed source with a wrong declaration** → `verify-source` reports declared-but-missing
  metrics, undeclared extras, and unit/currency/scale surprises, and exits non-zero. Normal
  renders never probe live to discover capabilities — they trust the declared `Capability`, so an
  un-verified declaration can only mislabel, never crash mid-render.
- **`.env` / secrets** → never committed (protected by `protect-files.sh`); never logged.

## 6. Verification

Prereq: toolchain installed (`uv`), deps synced.

```sh
uv sync
pytest -q          # all tests pass (unit tests use recorded fixtures, no live network)
ruff check         # clean
```

Source onboarding (live network, real keys in `.env`) — run for each source/market, expect a
clean report and exit 0:
```sh
python -m financial_charts verify-source yfinance   --ticker AAPL
python -m financial_charts verify-source yfinance   --ticker TEVA.TA --market TASE
python -m financial_charts verify-source twelvedata --ticker AAPL
python -m financial_charts verify-source twelvedata --ticker TEVA.TA --market TASE
```

End-to-end (live network, real keys in `.env`):
```sh
# US via free source
python -m financial_charts AAPL --source yfinance --period annual --range 10y --out out/AAPL.html
# TASE via paid source — verify ₪ units and agorot/millions handling
python -m financial_charts TEVA.TA --source twelvedata --period annual --range 10y --out out/TEVA.html
```
Expected: each writes a static HTML page showing the `"fundamentals"` chart grid; US page in
`$`, TASE page in `₪`; unavailable metrics show "No Data"; `source_limits` is listed. Open the
files and confirm the charts match the company's known financials and the TASE figures are
scaled correctly (not off by 100× or 1e6×).

Unit-level proof of the core risk: a `Money` test converting a known TASE agorot price to ILS
and asserting statements-in-millions are not mixed with price units.
```sh
pytest -q financial_charts/template/models_test.py
```
