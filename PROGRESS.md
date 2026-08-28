# Progress

SPEC.md tasks 1–15 are complete and committed (see git log). The tool is fully
functional end-to-end:

```sh
python -m financial_charts AAPL --source yfinance --range 10y --out out/AAPL.html
python -m financial_charts TEVA.TA --source twelvedata --range 10y --out out/TEVA.html
python -m financial_charts verify-source yfinance --ticker AAPL
```

## Web UI (step 1 — static)

*Superseded by step 2 below — the iframe and the static-PNG grid are gone.*

An independent `financial_charts/web/` module adds a browser UI. It composes only
the published interfaces of the existing modules (nothing else was modified) and has
its own entry point:

```sh
python -m financial_charts.web --port 8000   # then open the forwarded port
```

Enter a ticker + source/period/range/chart-set in the form; the dashboard renders in
an iframe below. Same static matplotlib PNG grid as the CLI. **Step 2 (future):**
interactive charts — add a JSON endpoint in this same `web/` module and swap the
front-end to a JS chart library; the template already serializes to JSON, so no
changes to sources/cache/template are needed.

Suite green, `ruff check` clean, `.claude` hooks wired to the uv toolchain. (No test count
here on purpose — it has gone stale twice; `pytest -q` is the authority.)

## Web UI (step 2 — interactive)

Done. The iframe/static-PNG dashboard is replaced with client-side Plotly.js
charts, exactly as step 1 anticipated — no changes to sources/cache/template/
charts/dashboard, all new code lives in `web/`. The CLI (`--out *.png/*.pdf/*.html`)
is untouched and stays static matplotlib.

- `web/chart_data.py` (new) shapes a `CompanyFundamentals` chart set into JSON,
  independent of every `charts/builtins/*.py` file — re-derived from the template
  (reusing `charts.base`'s published `currency_symbol`/`format_compact_number` and
  `template.derived`'s published `resolve`/`ratio`/`DerivedMetric` constants) rather
  than introspecting matplotlib `Axes` output, which would depend on an unpublished
  surface. A handful of charts (market cap, P/E, dividend yield, ROE, valuation's
  nearest-price join, price's SMA overlay) have their small inline math
  re-implemented here since it isn't externalized from their chart file today —
  an accepted, not eliminated, duplication/drift risk against those originals.
- **NaN → invalid JSON**: `flask.jsonify()` reproduces a raw `NaN` token for values
  like the SMA warm-up period (invalid per the JSON spec, breaks `JSON.parse`).
  Fixed by returning `ChartDataResponse.model_dump_json()` (Pydantic launders NaN
  to `null`) via a raw `Response`, never through `jsonify()`.
- New `GET /chart-data` route in `web/app.py`, alongside the unchanged `/render`
  (kept as a plain-HTML fallback). Both share a new `_resolve_request()` extracted
  from `/render`'s old body. While extracting it: `chart_set` was previously
  unvalidated (`?chart_set=bogus` → unhandled 500) — fixed as a small in-scope gap
  while already touching this validation code.
- `index.html`'s iframe is gone; the form fetches `/chart-data` and renders cards
  client-side. KPI charts render as plain HTML stat tiles (not Plotly traces) per
  the dataviz skill's guidance that a single current value is a stat tile, not a
  one-bar chart. Colors use the dataviz skill's validated categorical palette,
  deliberately dropping the matplotlib named colors (`"darkorange"` etc.) used
  today as per-card decoration. Dark mode re-themes via `prefers-color-scheme`
  (Plotly doesn't auto-theme) and re-renders the last response on an OS theme
  change. Plotly.js loads from its CDN pinned to an exact version (`plotly-basic-
  3.7.0.min.js`), not `plotly-latest`.
- **Deferred, not dropped**: no table-view accessibility fallback for the
  interactive charts (the dataviz skill's twin of every chart); no delta/sparkline
  on KPI stat tiles even though the underlying series exists.
- No JS test runner exists in this toolchain (plain Flask+Jinja2, no bundler) —
  the fetch+Plotly wiring is verified manually (`python -m financial_charts.web`),
  not by `pytest`.

## Web UI — chart picker layout + user-creatable chart sets

Done, two follow-ups from using the interactive dashboard:

- The checkbox picker was a single-column list of all 21 charts (~500px
  tall), pushing the rest of the form down. Now a `<details>`/`<summary>`
  popover (no JS needed to open/close) — collapsed by default to one line,
  opens as a `position: absolute` floating panel (a compact 3-column
  checkbox grid) so it overlays instead of displacing sibling fields.
  Pre-checked with `config.DEFAULT_CHART_SET`'s own members at page load.
- **The picker and the "Chart set" dropdown weren't actually connected** —
  the picker's checked state was a fixed snapshot taken once at page load,
  not reactive to the dropdown. Fixed: `index()` now passes a
  `chart_set_members` map (every registered set's own chart ids) as a JSON
  island; a `change` listener on the dropdown re-syncs the checkboxes to
  match. This also exposed that there was no way to *create* a new chart
  set — only `charts/registry.py`'s `register_chart_set()`, a Python-only
  function.
- New `web/chart_set_store.py` (`ChartSetStore`) — disk persistence for
  user-created chart sets, deliberately mirroring `cache/store.py`'s
  `TemplateCache` pattern (atomic temp-file-then-`os.replace` write,
  injectable directory, corrupt/missing file treated as empty rather than a
  crash), one JSON file in the same already-gitignored `.cache/financial_charts/`
  directory. `create_app()` takes an optional `chart_set_store` param
  (defaults to the real store) and re-registers every persisted set on
  startup via the existing published `register_chart_set()` — `charts/registry.py`
  itself is untouched. A chart id that no longer resolves (catalog changed
  since it was saved) is skipped, not a startup crash.
- New `POST /chart-sets` route + a small "Save as new set" row inside the
  picker popover: names the current checkbox selection, registers it live
  and persists it, and the front end inserts+selects the new `<option>`
  without a page reload.
- `web/app_test.py`'s `client` fixture now injects a `tmp_path`-backed
  `ChartSetStore` for every test in the file (not just the new ones) — the
  bootstrap-on-`create_app()` load means every test now indirectly touches
  chart-set persistence, and none of them should read or write the real
  local `.cache/financial_charts/chart_sets.json`.

## Task 16 — chart inventory (SPEC.md)

Done. The full inventory beyond the original six (Price, Revenue, Net Income,
FCF, EPS, Margins) is implemented, each its own vertical slice under
`charts/builtins/` following the `revenue.py`/`revenue_test.py` pattern:

- **EBITDA, Expenses (R&D/SG&A), Dividends Paid, Shares Outstanding** — reuse
  fields already present in the existing income-statement/cash-flow fetch
  calls in both adapters; no new endpoints needed.
- **Cash & Debt, Assets/Equity/Liabilities, Debt & Financial Leverage,
  Ratios (Current Ratio)** — added `balance_sheet` fetching to both adapters
  (yfinance's `balance_sheet`/`quarterly_balance_sheet` properties, Twelve
  Data's `balance_sheet` endpoint), exposing `total_assets`,
  `total_liabilities`, `total_equity`, `cash_and_equivalents`, `total_debt`,
  `total_current_assets`, `total_current_liabilities`, `ebit` as base
  metrics. Two new `DerivedMetric`s (`current_ratio`, `debt_to_equity`) in
  `template/derived.py`.
- **Return on Capital (ROIC/ROCE)** — ROCE is the standard EBIT / (Assets -
  Current Liabilities); ROIC is a simplification (Net Income / (Debt +
  Equity - Cash), documented in `derived.py`) that avoids fetching a
  separate effective tax rate for one chart.
- **Valuation (P/B)** — book value/share is a normal same-cadence derived
  metric, but pairing it with daily price needed nearest-date matching
  (statement dates rarely land on a trading day) — done locally in
  `valuation.py` rather than complicating `resolve()`'s exact-date join used
  by every other derived metric.
- **KPI cards** (Market Cap, P/E, Dividend Yield, ROE) — single-value "stat
  tile" cards; each is a normal `Chart` that draws a big number via two new
  shared helpers (`render_kpi_value`, `format_compact_number`) instead of a
  line/bar, so no dashboard/layout changes were needed. All four reuse
  metrics already fetched for other charts.

Building the KPI cards surfaced a real bug (now fixed, with a regression
test): yfinance's price series never filtered `NaN` closes — yfinance
returns one for the current, still-open trading day — so "latest price"
was silently NaN. Every other statement-series helper already filtered
`NaN`; `_price_series` didn't.

Capability declarations for both sources were hand-verified against live
bank/large-cap sample data (not `commission-source` — that tool's
metric-availability probe is scoped to `available_charts()`'s
`required_metrics`, so running it before a metric has a consuming chart
drops it from the regenerated `capability.py`; it's also stricter than the
existing declarations tolerate, e.g. it would drop `gross_margin` for
yfinance since bank samples lack a clean gross-profit line — a pre-existing
imprecision, not something to silently fix as a side effect of Task 16).

## Price-chart follow-ups

Two fixes from using the dashboard on real tickers, both in the price slice:

- **SMA overlay styling** (`ecc2e96`). The SMAs were drawn at the same weight as
  the Close line — and on the web with a marker per point — burying the primary
  series. Series specs now carry optional width/markers drawing hints, so the
  price slice owns its own styling instead of the front-end pattern-matching
  `"SMA "` labels.
- **Daily bars from Twelve Data at every range** (`00a2a53`). The SMA overlays
  count *points*, not days, so Twelve Data's per-range interval (weekly at 3y/5y,
  monthly at 10y/max) silently turned "SMA 50" into a 50-week or 50-month
  average and dropped SMA 150/200 entirely for want of bars — while yfinance,
  always daily, drew all three. Every range now requests `1day` bars with a
  per-range `outputsize`. Verified live: `outputsize` caps at 5000, behaves the
  same on TASE (`mic_code=XTAE`), and `time_series` bills per request rather
  than per point, so this costs no extra credits.

## Documentation re-evaluation (2026-08-02)

`Project_ReEvaluation_2026-08-02.md` audited the docs against the code and found
the drift concentrated in `README.md`, which still described the pre-Plotly,
pre-task-16 project. Its recommendations are applied: README/CLAUDE.md/SPEC.md
corrected, the three undocumented CLI subcommands and `--charts` documented, a
committed `.env.example` added, and two coverage gaps closed with
`sources/currency_test.py` (the agorot→ILS mapping) plus range-boundary
assertions in `ranges_test.py`. SPEC task 6's "TASE prices only" wording was
amended rather than the declaration narrowed — see the note in SPEC.md.

## Trailing-TTM historical charts (Market Cap, P/E, Dividend Yield, ROE)

Done. These four were the only charts in the catalog still reading `.points[-1]`
for a single "KPI" stat-tile value instead of a historical series — P/E labeled
itself "Trailing" but was really price over one period's EPS (annual or a single
quarter's, whichever `--period` fetched). All four are now historical line charts
of trailing-twelve-month values, sampled daily against price where price is a
meaningful driver:

- New `template/trailing.py`, a sibling of `template/derived.py`: `ttm_series()`
  turns a flow metric (EPS, net income, dividends paid) into a rolling
  trailing-twelve-month view — identity under `Period.ANNUAL` (an annual figure
  already *is* trailing-twelve-months at its fiscal date), a gap-guarded rolling
  4-quarter sum under `Period.QUARTERLY` (a window spanning >330 days is missing
  a quarter and is skipped rather than silently understated).
  `TrailingMetric`/`resolve_trailing()` then join a daily driver series (`price`)
  against other inputs *as of* each driver date — the most recent statement value
  known on or before that date, via `bisect`, never a future one (no lookahead).
  ROE has no natural daily driver, so its `TrailingMetric.driver=None` and it
  stays at statement cadence instead of manufacturing a false daily density.
- The four `charts/builtins/*.py` files and their `web/chart_data.py` shapers now
  do zero math — they resolve the shared `PE_RATIO_TTM`/`MARKET_CAP`/
  `DIVIDEND_YIELD_TTM`/`ROE_TTM` constants and draw the result, removing them
  from the web/matplotlib duplication list below (only valuation's nearest-price
  join and price's SMA overlay remain hand-duplicated).
- The now-unused KPI stat-tile surface was removed as dead code created by this
  change: `render_kpi_value`/`format_compact_number` (`charts/base.py`),
  `KpiChartSpec`, and the `.stat-tile` CSS/JS branch in `index.html`.
- **Fixed during review**: a per-date compute failure (a loss year's
  non-positive TTM EPS, a zero-equity/zero-price date) was being dropped from
  the point list entirely, which let the line renderer draw a straight
  segment connecting the surrounding valid points *through* the undefined
  date — e.g. P/E gliding smoothly across an entire loss year instead of
  showing no value for it. `resolve_trailing` now emits `float("nan")` for
  that date instead (the same break-the-line convention the price chart's
  SMA warm-up already relies on); a series where *every* date fails still
  collapses to `available=False`/"No Data", unchanged from before.
- Not done, flagged as a natural follow-up: `valuation.py`'s hand-rolled
  nearest-price join could move onto the same as-of join `resolve_trailing` now
  provides, instead of its own bespoke `_nearest_price`.

## Remaining work

No known gaps. Nothing half-done — safe to stop or resume at any point.
