# Project Re-Evaluation — Financial Charts

**Date:** 2026-08-02
**Focus:** Full Project
**Previous Reports:** None — this is the first re-evaluation and establishes the baseline.
**Status:** Recommendations applied 2026-08-02 — all of Priority 1–4 and 6.1/6.2. Two items
closed without an edit: 6.3 (the catalog is already pinned by name, not just count, in
`catalog_test.py`) and 6.4 (no action recommended). 3.6 was decided in favour of amending the
SPEC; the rationale is now recorded in SPEC.md task 6. The findings tables below are left as
the as-audited record — read them together with this status line, not as current state.

## Executive Summary

The code is in good shape and the *deep* documentation is accurate: `SPEC.md`'s key interfaces,
error types, `Money` API, `CompanyFundamentals` field list, capability history depths (free 4y /
paid 10y), SMA windows, the agorot rule, and the Plotly version pin all match the code exactly.
288 tests pass, and only three non-`__init__` modules lack a colocated test.

The drift is concentrated almost entirely in **`README.md`, which describes a version of this
project that stopped existing several features ago.** It tells a reader the web UI is static
matplotlib PNGs ([README.md:45](README.md#L45), [README.md:52-53](README.md#L52-L53),
[README.md:89-90](README.md#L89-L90)) and leaves both "Remaining inventory charts" and
"Interactive web charts" unchecked ([README.md:108-109](README.md#L108-L109)) — while
`PROGRESS.md` records both as *done* and the code confirms it (21 charts in
[catalog.py:28-50](src/financial_charts/charts/catalog.py#L28-L50); Plotly at
[index.html:139](src/financial_charts/web/templates/index.html#L139)). A new reader is
misinformed about the project's headline capability.

The **highest-impact gap** is subtler and appears in no document at all: the catalog holds **21
charts**, but the default `"fundamentals"` set renders **6** of them
([registry.py:16-23](src/financial_charts/charts/registry.py#L16-L23)). The `--charts` flag that
reaches the other 15 is undocumented in both `README.md` and `CLAUDE.md`. A user following the
README today gets 6 charts, is told the tool renders "a fixed grid of charts all at once", and
has no documented way to discover the remaining 15. Two further CLI subcommands — `capabilities`
and `commission-source` — are likewise entirely absent from the user-facing docs.

Secondary: `PROGRESS.md` says 240 tests (actual 288), `CLAUDE.md`'s cache key omits period+range,
and `CLAUDE.md:6-8` still carries a pre-scaffold note claiming there is no `pyproject.toml` and
that the charting library and paid source are undecided — all three long since settled.

---

## Findings

### 1. Documentation Accuracy

| # | Doc claim | Doc location | Code reality | Code location | Status |
|---|---|---|---|---|---|
| 1.1 | "240 tests passing" | [PROGRESS.md:28](PROGRESS.md#L28) | 288 tests collected | `pytest --collect-only -q` | **Mismatch** |
| 1.2 | `[ ] Remaining inventory charts (SPEC task 16: EBITDA, dividends, ratios, KPI cards, …)` | [README.md:108](README.md#L108) | All 21 charts implemented and registered | [catalog.py:28-50](src/financial_charts/charts/catalog.py#L28-L50) | **Mismatch** |
| 1.3 | `[ ] Interactive web charts (web step 2)` | [README.md:109](README.md#L109) | Step 2 complete; client-side Plotly | [index.html:139](src/financial_charts/web/templates/index.html#L139), [PROGRESS.md:30-33](PROGRESS.md#L30-L33) | **Mismatch** |
| 1.4 | "what's next (task 16: expanding the chart inventory; step 2: interactive web charts)" | [README.md:97-99](README.md#L97-L99) | Both done | [PROGRESS.md:32](PROGRESS.md#L32), [PROGRESS.md:111](PROGRESS.md#L111) | **Mismatch** |
| 1.5 | "The charts themselves are **static** (matplotlib PNGs); the web UI is a front-end that drives static renders, not an interactive charting app." | [README.md:89-90](README.md#L89-L90) | Web UI is interactive Plotly (hover/zoom/legend) | [index.html:285](src/financial_charts/web/templates/index.html#L285) | **Mismatch** |
| 1.6 | Heading "Web UI — a browser front-end (static charts)" | [README.md:45](README.md#L45) | Interactive | [index.html:285](src/financial_charts/web/templates/index.html#L285) | **Mismatch** |
| 1.7 | "It serves the same static chart grid as the CLI." | [README.md:52-53](README.md#L52-L53) | Serves JSON via `/chart-data`, rendered client-side | [app.py:199](src/financial_charts/web/app.py#L199) | **Mismatch** |
| 1.8 | "the dashboard renders in an iframe below" | [PROGRESS.md:23](PROGRESS.md#L23) | Iframe removed in step 2 — contradicted 32 lines later by [PROGRESS.md:55](PROGRESS.md#L55) | [index.html](src/financial_charts/web/templates/index.html) (no iframe) | **Mismatch** (internal to one doc) |
| 1.9 | Cache "keyed by ticker + source + date" | [CLAUDE.md:70](CLAUDE.md#L70) | `(ticker, source, period, range, date)` | [store.py:10-13](src/financial_charts/cache/store.py#L10-L13) | **Mismatch** |
| 1.10 | "there is no pyproject.toml yet, so the commands are not runnable until the project is scaffolded. Charting library and paid data source are still TBD." | [CLAUDE.md:6-8](CLAUDE.md#L6-L8) | `pyproject.toml` exists; matplotlib + Plotly.js; Twelve Data chosen | [pyproject.toml:1-20](pyproject.toml#L1-L20) | **Mismatch** |
| 1.11 | yfinance capability declares "US strong, TASE prices only / sparse fundamentals" | [SPEC.md:172-173](SPEC.md#L172-L173) | Declares all 20 metrics for **both** markets; sparseness is only a code comment | [yfinance/capability.py:9-33](src/financial_charts/sources/yfinance/capability.py#L9-L33) | **Mismatch** |
| 1.12 | "renders a fixed, pre-determined grid of charts *all at once*" | [README.md:3-5](README.md#L3-L5), [SPEC.md:9-10](SPEC.md#L9-L10) | Default `"fundamentals"` set = 6 charts of 21 available | [registry.py:16-23](src/financial_charts/charts/registry.py#L16-L23) | **Incomplete** |
| 1.13 | Free = 4y, paid = 10y history | [README.md:77](README.md#L77), [CLAUDE.md:63-64](CLAUDE.md#L63-L64) | `ANNUAL: 4` / `ANNUAL: 10` | [yfinance/capability.py:11](src/financial_charts/sources/yfinance/capability.py#L11), [twelvedata/capability.py:8](src/financial_charts/sources/twelvedata/capability.py#L8) | Match |
| 1.14 | Price chart has SMA 50/150/200 | [SPEC.md:186](SPEC.md#L186) | `_SMA_WINDOWS = (50, 150, 200)` | [price.py:7](src/financial_charts/charts/builtins/price.py#L7) | Match |
| 1.15 | "Requires Python 3.12+" | [README.md:12](README.md#L12) | `requires-python = ">=3.12"` | [pyproject.toml:8](pyproject.toml#L8) | Match |
| 1.16 | Ranges `6m\|1y\|3y\|5y\|10y\|max` | [README.md:38](README.md#L38) | Identical tuple | [ranges.py:8](src/financial_charts/sources/ranges.py#L8) | Match |
| 1.17 | Plotly pinned to `plotly-basic-3.7.0.min.js`, not `plotly-latest` | [PROGRESS.md:62-63](PROGRESS.md#L62-L63) | Exact pin | [index.html:139](src/financial_charts/web/templates/index.html#L139) | Match |
| 1.18 | "all 21 charts" in the picker | [PROGRESS.md:75](PROGRESS.md#L75) | 21 entries | [catalog.py:28-50](src/financial_charts/charts/catalog.py#L28-L50) | Match |
| 1.19 | `--period ttm` fails with "source does not support period ttm" | [README.md:41-43](README.md#L41-L43), [SPEC.md:36-38](SPEC.md#L36-L38) | Exact string | [validation.py:17](src/financial_charts/sources/validation.py#L17) | Match |
| 1.20 | `CompanyFundamentals(ticker, market, currency, period, range, series, source_limits)` | [SPEC.md:117](SPEC.md#L117) | Exactly those 7 fields | [models.py:143-149](src/financial_charts/template/models.py#L143-L149) | Match |
| 1.21 | Original six charts = Price, Revenue, Net Income, FCF, EPS, Margins | [SPEC.md:186-187](SPEC.md#L186-L187), [PROGRESS.md:111-112](PROGRESS.md#L111-L112) | Exactly the `"fundamentals"` set | [registry.py:16-23](src/financial_charts/charts/registry.py#L16-L23) | Match |

### 2. Undocumented Code

| # | Item | Code location | Doc coverage | Status |
|---|---|---|---|---|
| 2.1 | `capabilities` CLI subcommand | [__main__.py:263-265](src/financial_charts/__main__.py#L263-L265) | Absent from README.md and CLAUDE.md | **Missing** |
| 2.2 | `commission-source` CLI subcommand | [__main__.py:337-341](src/financial_charts/__main__.py#L337-L341) | Only a parenthetical caveat at [PROGRESS.md:148](PROGRESS.md#L148) | **Missing** |
| 2.3 | `--charts` flag (comma-separated chart ids, overrides `--chart-set`) | [__main__.py:58-62](src/financial_charts/__main__.py#L58-L62) | Absent from the CLI synopsis at [README.md:38-39](README.md#L38-L39) and [CLAUDE.md:17](CLAUDE.md#L17) | **Missing** |
| 2.4 | Explicit `render` subcommand | [__main__.py:403-404](src/financial_charts/__main__.py#L403-L404) | Undocumented (only the implicit bare form is shown) | **Missing** |
| 2.5 | `--chart-set` flag | [__main__.py:55-57](src/financial_charts/__main__.py#L55-L57) | In README.md:39, omitted from [CLAUDE.md:17](CLAUDE.md#L17) | **Incomplete** |
| 2.6 | `chart_support.py` | [chart_support.py:1](src/financial_charts/chart_support.py#L1) | Not in the SPEC module layout ([SPEC.md:62-91](SPEC.md#L62-L91)) | **Missing** |
| 2.7 | `charts/catalog.py` | [catalog.py:1](src/financial_charts/charts/catalog.py#L1) | Not in SPEC module layout | **Missing** |
| 2.8 | `template/derived.py` (7 derived metrics) | [derived.py:1](src/financial_charts/template/derived.py#L1) | Not in SPEC module layout; formulas described in PROGRESS.md only | **Missing** |
| 2.9 | `sources/ranges.py` | [ranges.py:1](src/financial_charts/sources/ranges.py#L1) | Not in SPEC module layout | **Missing** |
| 2.10 | `sources/currency.py` | [currency.py:1](src/financial_charts/sources/currency.py#L1) | Not in SPEC module layout | **Missing** |
| 2.11 | `sources/commission.py` | [commission.py:1](src/financial_charts/sources/commission.py#L1) | Not in SPEC module layout | **Missing** |
| 2.12 | `web/` package (7 modules) | `src/financial_charts/web/` | README §Web UI + PROGRESS.md cover it; absent from SPEC module layout | **Incomplete** |
| 2.13 | `flask` runtime dependency | [pyproject.toml:10](pyproject.toml#L10) | SPEC dependency list ([SPEC.md:156-158](SPEC.md#L156-L158)) omits it | **Missing** |
| 2.14 | Plotly.js (CDN asset, not a Python dep) | [index.html:139](src/financial_charts/web/templates/index.html#L139) | PROGRESS.md only; README's Architecture never mentions it | **Incomplete** |
| 2.15 | `UnsupportedPeriod` exception | [base.py:46](src/financial_charts/sources/base.py#L46) | [SPEC.md:101](SPEC.md#L101) lists only 3 of the 4 error types | **Missing** |
| 2.16 | `GET /chart-data` and `POST /chart-sets` routes | [app.py:199](src/financial_charts/web/app.py#L199), [app.py:217](src/financial_charts/web/app.py#L217) | PROGRESS.md only; README's Web UI section describes neither | **Incomplete** |
| 2.17 | `requests` dependency (Twelve Data REST) | [pyproject.toml:15](pyproject.toml#L15) | [SPEC.md:157](SPEC.md#L157) explicitly permits "or `requests` for its REST API" | Match |

### 3. Dead References

| # | Doc reference | Doc location | Present in code? | Status |
|---|---|---|---|---|
| 3.1 | "the dashboard renders in an iframe below" | [PROGRESS.md:23](PROGRESS.md#L23) | No — removed in step 2, per [PROGRESS.md:55](PROGRESS.md#L55) in the same file | **Dead** |
| 3.2 | Web UI serves "static matplotlib PNGs" | [README.md:89-90](README.md#L89-L90) | No — that path is JSON + Plotly | **Dead** |
| 3.3 | Hooks configured as `TEST_CMD="pytest -q"`, `FORMAT_CMD="ruff format"` | [SPEC.md:192-193](SPEC.md#L192-L193) | Real values are venv-absolute (`$CLAUDE_PROJECT_DIR/.venv/bin/pytest -q`) | **Incomplete** |
| 3.4 | `Money.to(scale)` | [SPEC.md:114](SPEC.md#L114) | [models.py:51](src/financial_charts/template/models.py#L51) | Match |
| 3.5 | `TickerNotFound`, `SourceUnavailable`, `MissingCredentials` | [SPEC.md:101](SPEC.md#L101) | [base.py:34,38,42](src/financial_charts/sources/base.py#L34-L42) | Match |
| 3.6 | `require_supported_period` | [SPEC.md:37](SPEC.md#L37) | [validation.py:6](src/financial_charts/sources/validation.py#L6) | Match |
| 3.7 | `register_chart_set()` | [PROGRESS.md:87](PROGRESS.md#L87), [PROGRESS.md:95](PROGRESS.md#L95) | [registry.py:27](src/financial_charts/charts/registry.py#L27) | Match |
| 3.8 | `config.DEFAULT_CHART_SET` | [PROGRESS.md:80](PROGRESS.md#L80) | [config.py:9](src/financial_charts/config.py#L9) | Match |
| 3.9 | `sources/validation.py` vs `sources/verify.py` split | [SPEC.md:103-110](SPEC.md#L103-L110) | Both exist with the described split | Match |
| 3.10 | `charts/builtins/` file list (price, revenue, net_income, free_cash_flow, eps, margins) | [SPEC.md:85](SPEC.md#L85) | All six exist, plus 15 more | Match |

### 4. Configuration Alignment

There is **no `.env.example` or `.env.template`** in the repo — the only env-var template is the
fenced block at [README.md:20-25](README.md#L20-L25). A new contributor has nothing to copy.

| # | Env var | In `.env` | In `config.py` | Read by code at | Documented at | Status |
|---|---|---|---|---|---|---|
| 4.1 | `TWELVEDATA_API_KEY` | Yes | No | [twelvedata/adapter.py:51](src/financial_charts/sources/twelvedata/adapter.py#L51) | [README.md:23](README.md#L23), [SPEC.md:139](SPEC.md#L139) | Match |
| 4.2 | `DATA_SOURCE` | No | Yes (default `"yfinance"`) | [config.py:13](src/financial_charts/config.py#L13) | [README.md:24](README.md#L24), [SPEC.md:24](SPEC.md#L24) | **Incomplete** — documented and defaulted, but absent from the actual `.env` |
| 4.3 | `config.py` described as holding "DATA_SOURCE, API keys, defaults" | — | Holds only `DATA_SOURCE` + 3 defaults | API key read directly by the adapter | [SPEC.md:67](SPEC.md#L67) | **Mismatch** |
| 4.4 | No env var is read anywhere outside `config.py` and `twelvedata/adapter.py` | — | — | verified by grep over `src/**/*.py` | — | Match (no undocumented vars) |

### 5. Constants & Weights Verification

| # | Constant / formula | Documented as | Doc location | Coded as | Code location | Status |
|---|---|---|---|---|---|---|
| 5.1 | SMA windows | 50 / 150 / 200 | [SPEC.md:186](SPEC.md#L186) | `(50, 150, 200)` | [price.py:7](src/financial_charts/charts/builtins/price.py#L7) | Match |
| 5.2 | yfinance annual history | 4y | [README.md:77](README.md#L77) | `Period.ANNUAL: 4` | [yfinance/capability.py:11](src/financial_charts/sources/yfinance/capability.py#L11) | Match |
| 5.3 | Twelve Data annual history | 10y | [README.md:77](README.md#L77) | `Period.ANNUAL: 10` | [twelvedata/capability.py:8](src/financial_charts/sources/twelvedata/capability.py#L8) | Match |
| 5.4 | Quarterly history depth (both sources) | not documented | — | `QUARTERLY: 4` / `QUARTERLY: 10` | [yfinance/capability.py:11](src/financial_charts/sources/yfinance/capability.py#L11), [twelvedata/capability.py:8](src/financial_charts/sources/twelvedata/capability.py#L8) | **Missing** |
| 5.5 | Agorot conversion | 1 agora = 1/100 ₪ | [CLAUDE.md:119-120](CLAUDE.md#L119-L120), [SPEC.md:125](SPEC.md#L125) | `AGOROT_CODE = "ILA"`, ÷100 at the adapter | [currency.py:5-7](src/financial_charts/sources/currency.py#L5-L7) | Match |
| 5.6 | ROCE = EBIT / (Total Assets − Current Liabilities) | same | [PROGRESS.md:126-127](PROGRESS.md#L126-L127) | same | [derived.py:100-103](src/financial_charts/template/derived.py#L100-L103) | Match |
| 5.7 | ROIC = Net Income / (Debt + Equity − Cash) | same, flagged as a simplification | [PROGRESS.md:127-129](PROGRESS.md#L127-L129) | same, same caveat in docstring | [derived.py:106-115](src/financial_charts/template/derived.py#L106-L115) | Match |
| 5.8 | Two new derived metrics in task 16 (`current_ratio`, `debt_to_equity`) | 2 | [PROGRESS.md:124-125](PROGRESS.md#L124-L125) | 2 added; 7 total | [derived.py:85-97](src/financial_charts/template/derived.py#L85-L97) | Match |
| 5.9 | Plotly categorical palette | "dataviz skill's validated categorical palette" | [PROGRESS.md:57-59](PROGRESS.md#L57-L59) | 8 hex values | [index.html:143-144](src/financial_charts/web/templates/index.html#L143-L144) | Match |
| 5.10 | Default period / range / chart set | not in README or CLAUDE.md | — | `annual` / `5y` / `fundamentals` | [config.py:7-9](src/financial_charts/config.py#L7-L9) | **Missing** |
| 5.11 | `range_years("6m")` | not documented | — | `1` (rounds a half-year up to 1) | [ranges.py:11](src/financial_charts/sources/ranges.py#L11) | **Missing** |
| 5.12 | `range_years("max")` | not documented | — | `10_000` (sentinel) | [ranges.py:16](src/financial_charts/sources/ranges.py#L16) | **Missing** |
| 5.13 | Dashboard grid columns | not documented | — | `2` | [layout.py:16](src/financial_charts/dashboard/layout.py#L16) | **Missing** |
| 5.14 | Card figure size / DPI | not documented | — | `(5, 3.2)` / `110` | [layout.py:17](src/financial_charts/dashboard/layout.py#L17), [layout.py:36](src/financial_charts/dashboard/layout.py#L36) | **Missing** |
| 5.15 | Default chart-set size | not stated anywhere | — | 6 charts | [registry.py:16-23](src/financial_charts/charts/registry.py#L16-L23) | **Missing** |
| 5.16 | Catalog size | 21 | [PROGRESS.md:75](PROGRESS.md#L75) | 21 | [catalog.py:28-50](src/financial_charts/charts/catalog.py#L28-L50) | Match |
| 5.17 | `CUSTOM_CHART_SET_PREFIX` | not documented | — | `"custom:"` | [registry.py:8](src/financial_charts/charts/registry.py#L8) | **Missing** (internal; low value to document) |

### 6. Test Coverage

**288 tests collected** across **46 test files** (`pytest --collect-only -q`). Suite is green:
`288 passed in 9.27s`.

#### Per-file breakdown

| Test file | Tests |
|---|---|
| [web/app_test.py](src/financial_charts/web/app_test.py) | 36 |
| [__main___test.py](src/financial_charts/__main___test.py) | 28 |
| [web/chart_data_test.py](src/financial_charts/web/chart_data_test.py) | 18 |
| [template/derived_test.py](src/financial_charts/template/derived_test.py) | 16 |
| [sources/commission_test.py](src/financial_charts/sources/commission_test.py) | 13 |
| [sources/verify_test.py](src/financial_charts/sources/verify_test.py) | 11 |
| [template/models_test.py](src/financial_charts/template/models_test.py) | 10 |
| [sources/twelvedata/adapter_test.py](src/financial_charts/sources/twelvedata/adapter_test.py) | 10 |
| [sources/registry_test.py](src/financial_charts/sources/registry_test.py) | 9 |
| [web/chart_set_store_test.py](src/financial_charts/web/chart_set_store_test.py) | 8 |
| [charts/base_test.py](src/financial_charts/charts/base_test.py) | 8 |
| [cache/store_test.py](src/financial_charts/cache/store_test.py) | 8 |
| [sources/yfinance/adapter_test.py](src/financial_charts/sources/yfinance/adapter_test.py) | 7 |
| [sources/validation_test.py](src/financial_charts/sources/validation_test.py) | 7 |
| [sources/market_test.py](src/financial_charts/sources/market_test.py) | 7 |
| [sources/ranges_test.py](src/financial_charts/sources/ranges_test.py) | 6 |
| [web/service_test.py](src/financial_charts/web/service_test.py) | 5 |
| [dashboard/render_test.py](src/financial_charts/dashboard/render_test.py) | 5 |
| [charts/registry_test.py](src/financial_charts/charts/registry_test.py) | 5 |
| [chart_support_test.py](src/financial_charts/chart_support_test.py) | 5 |
| [charts/builtins/valuation_test.py](src/financial_charts/charts/builtins/valuation_test.py) | 4 |
| [charts/builtins/dividend_yield_test.py](src/financial_charts/charts/builtins/dividend_yield_test.py) | 4 |
| [dashboard/layout_test.py](src/financial_charts/dashboard/layout_test.py) | 3 |
| [config_test.py](src/financial_charts/config_test.py) | 3 |
| [charts/catalog_test.py](src/financial_charts/charts/catalog_test.py) | 3 |
| [charts/builtins/return_on_equity_test.py](src/financial_charts/charts/builtins/return_on_equity_test.py) | 3 |
| [charts/builtins/return_on_capital_test.py](src/financial_charts/charts/builtins/return_on_capital_test.py) | 3 |
| [charts/builtins/ratios_test.py](src/financial_charts/charts/builtins/ratios_test.py) | 3 |
| [charts/builtins/price_test.py](src/financial_charts/charts/builtins/price_test.py) | 3 |
| [charts/builtins/pe_ratio_test.py](src/financial_charts/charts/builtins/pe_ratio_test.py) | 3 |
| [charts/builtins/fcf_margin_test.py](src/financial_charts/charts/builtins/fcf_margin_test.py) | 3 |
| [charts/builtins/debt_leverage_test.py](src/financial_charts/charts/builtins/debt_leverage_test.py) | 3 |
| [web/__main___test.py](src/financial_charts/web/__main___test.py) | 2 |
| [sources/base_test.py](src/financial_charts/sources/base_test.py) | 2 |
| [charts/builtins/shares_outstanding_test.py](src/financial_charts/charts/builtins/shares_outstanding_test.py) | 2 |
| [charts/builtins/revenue_test.py](src/financial_charts/charts/builtins/revenue_test.py) | 2 |
| [charts/builtins/net_income_test.py](src/financial_charts/charts/builtins/net_income_test.py) | 2 |
| [charts/builtins/market_cap_test.py](src/financial_charts/charts/builtins/market_cap_test.py) | 2 |
| [charts/builtins/margins_test.py](src/financial_charts/charts/builtins/margins_test.py) | 2 |
| [charts/builtins/free_cash_flow_test.py](src/financial_charts/charts/builtins/free_cash_flow_test.py) | 2 |
| [charts/builtins/expenses_test.py](src/financial_charts/charts/builtins/expenses_test.py) | 2 |
| [charts/builtins/eps_test.py](src/financial_charts/charts/builtins/eps_test.py) | 2 |
| [charts/builtins/ebitda_test.py](src/financial_charts/charts/builtins/ebitda_test.py) | 2 |
| [charts/builtins/dividends_test.py](src/financial_charts/charts/builtins/dividends_test.py) | 2 |
| [charts/builtins/cash_and_debt_test.py](src/financial_charts/charts/builtins/cash_and_debt_test.py) | 2 |
| [charts/builtins/assets_equity_liabilities_test.py](src/financial_charts/charts/builtins/assets_equity_liabilities_test.py) | 2 |
| **Total** | **288** |

#### Coverage gaps

| # | Module with no colocated test | Location | Assessment |
|---|---|---|---|
| 6.1 | `sources/currency.py` | [currency.py:1](src/financial_charts/sources/currency.py#L1) | Real gap. `map_currency` is the single point where the agorot (`"ILA"`) → ILS decision is made — the project's stated core risk ([CLAUDE.md:119-121](CLAUDE.md#L119-L121)). Exercised only indirectly via adapter tests. |
| 6.2 | `sources/yfinance/capability.py` | [yfinance/capability.py:1](src/financial_charts/sources/yfinance/capability.py#L1) | Low risk — a pure declaration, covered indirectly by `validation_test.py` and `chart_support_test.py`. |
| 6.3 | `sources/twelvedata/capability.py` | [twelvedata/capability.py:1](src/financial_charts/sources/twelvedata/capability.py#L1) | Same as above. |
| 6.4 | `web/templates/index.html` (fetch + Plotly wiring) | [index.html:139-285](src/financial_charts/web/templates/index.html#L139-L285) | Acknowledged and accepted at [PROGRESS.md:67-69](PROGRESS.md#L67-L69) — no JS test runner in this toolchain; verified manually. |

Every other non-`__init__` module has a colocated `*_test.py`.

---

## Comparison with Previous Reports

No prior `Project_ReEvaluation_*.md` reports exist in the project root. This report is the
baseline; subsequent audits should compare their findings against the tables above.

For reference, the drift measured here accumulated over 50 commits, with the most recent
documentation-affecting work being the web UI step 2 (Plotly) and task 16 (chart inventory).
Note also that the two most recent commits — `ecc2e96` (SMA overlay styling) and `00a2a53`
(daily price bars from Twelve Data at every range) — landed after `PROGRESS.md`'s final
"Remaining work: No known gaps" section ([PROGRESS.md:156-158](PROGRESS.md#L156-L158)) and are
not recorded in it.

---

## Recommendations

### Priority 1 — User-facing docs (`README.md`)

1.1 **[README.md:45](README.md#L45)** — change the heading
`### Web UI — a browser front-end (static charts)` to
`### Web UI — an interactive browser dashboard`.

1.2 **[README.md:51-54](README.md#L51-L54)** — replace "It serves the same static chart grid as
the CLI." with: "Charts are interactive (hover, zoom, legend toggle), rendered client-side with
Plotly.js from a `GET /chart-data` JSON endpoint; the CLI's `--out` export stays static
matplotlib. This is a self-contained module (`financial_charts/web/`) with its own entry point —
a local dev server, not for production."

1.3 **[README.md:89-91](README.md#L89-L91)** — replace "The charts themselves are **static**
(matplotlib PNGs); the web UI is a front-end that drives static renders, not an interactive
charting app." with: "The CLI's output is **static** (matplotlib PNG/HTML/PDF); the browser
dashboard is **interactive** (Plotly.js, loaded from CDN and pinned to `plotly-basic-3.7.0`),
reading the same canonical template through a JSON endpoint."

1.4 **[README.md:108-109](README.md#L108-L109)** — flip both checkboxes to done and restate:
`- [x] Full 21-chart inventory (SPEC task 16: EBITDA, dividends, ratios, KPI cards, …)` and
`- [x] Interactive web charts (web step 2 — Plotly.js)`.

1.5 **[README.md:97-99](README.md#L97-L99)** — the Status paragraph still names task 16 and web
step 2 as upcoming. Replace with: "Core spec (SPEC.md tasks 1–16) is complete, plus an
interactive browser UI. See [PROGRESS.md](PROGRESS.md) for the full history."

1.6 **[README.md:38-39](README.md#L38-L39)** — the CLI synopsis omits `--charts`. Change to:
`TICKER [--source] [--period quarterly|ttm|annual] [--range 6m|1y|3y|5y|10y|max] [--chart-set]
[--charts price,eps,margins] [--out PATH]`, and add a sentence: "The default `fundamentals`
chart set renders 6 charts; the catalog holds 21. Use `--charts` with a comma-separated list, or
the web UI's checkbox picker, to render any other combination." **This is the highest-impact fix
in the report** — see finding 1.12.

1.7 **[README.md:56-66](README.md#L56-L66)** — the `verify-source` section is the only subcommand
documented. Add two short subsections for the other developer commands: `capabilities` (prints a
registered source's declared `Capability`, offline, no credentials —
[__main__.py:263-265](src/financial_charts/__main__.py#L263-L265)) and `commission-source`
(probes a source live across sample tickers and generates its `capability.py` —
[__main__.py:337-341](src/financial_charts/__main__.py#L337-L341)). For `commission-source`,
carry over the caveat already recorded at [PROGRESS.md:148-154](PROGRESS.md#L148-L154): it is
scoped to `available_charts()`'s `required_metrics`, so running it before a metric has a
consuming chart silently drops that metric.

1.8 **[README.md:20-25](README.md#L20-L25)** — add a `.env.example` to the repo containing
`TWELVEDATA_API_KEY=` and `DATA_SOURCE=yfinance`, and change this block to say "copy
`.env.example` to `.env` and fill it in". See finding 4.2.

### Priority 2 — Internal/developer docs (`CLAUDE.md`)

2.1 **[CLAUDE.md:6-8](CLAUDE.md#L6-L8)** — delete the entire stale HTML comment. All three of its
claims are now false: `pyproject.toml` exists, the charting library is decided (matplotlib for
the CLI, Plotly.js for the web), and the paid source is Twelve Data.

2.2 **[CLAUDE.md:70-71](CLAUDE.md#L70-L71)** — correct the cache key. Change "keyed by ticker +
source + date" to "keyed by ticker + source + period + range + date", matching
[store.py:10-13](src/financial_charts/cache/store.py#L10-L13) and
[README.md:86-87](README.md#L86-L87).

2.3 **[CLAUDE.md:17](CLAUDE.md#L17)** — the CLI command line lists only
`[--source --period --range --out]`. Add the two missing flags:
`[--source --period --range --chart-set --charts --out]`.

2.4 **[CLAUDE.md:10-19](CLAUDE.md#L10-L19)** — the Commands section lists only `verify-source`
among subcommands. Add `python -m financial_charts capabilities [<name>]` and
`python -m financial_charts commission-source <name>`.

2.5 **[CLAUDE.md:77-79](CLAUDE.md#L77-L79)** — "Decided there: **static** output (matplotlib +
HTML/PNG/PDF)" is now only half true. Qualify it: "**static** CLI output (matplotlib +
HTML/PNG/PDF); the browser dashboard in `web/` is interactive (Plotly.js)".

### Priority 3 — Other project docs (`PROGRESS.md`, `SPEC.md`)

3.1 **[PROGRESS.md:28](PROGRESS.md#L28)** — "240 tests passing" → "288 tests passing". Consider
dropping the absolute number entirely; it has now gone stale twice-over and the suite is the
authority.

3.2 **[PROGRESS.md:22-23](PROGRESS.md#L22-L23)** — internal contradiction within one file: the
step-1 section says the dashboard "renders in an iframe below", which [line 55](PROGRESS.md#L55)
then reports as removed. Add a leading marker to the step-1 section, e.g. "*(superseded by step 2
below — the iframe is gone)*", so a reader isn't misled by the first section they reach.

3.3 **[PROGRESS.md:156-158](PROGRESS.md#L156-L158)** — the "Remaining work: No known gaps" section
predates commits `ecc2e96` (SMA overlays drawn as thin markerless lines) and `00a2a53` (daily
price bars fetched from Twelve Data at every range). Add a short section recording both.

3.4 **[SPEC.md:62-91](SPEC.md#L62-L91)** — the module layout is missing seven real modules. Add
`chart_support.py`, `charts/catalog.py`, `template/derived.py`, `sources/ranges.py`,
`sources/currency.py`, `sources/commission.py`, and the `web/` package.

3.5 **[SPEC.md:101](SPEC.md#L101)** — the error-type list names three exceptions; add
`UnsupportedPeriod` ([base.py:46](src/financial_charts/sources/base.py#L46)), which is the one a
user actually hits today via `--period ttm`.

3.6 **[SPEC.md:172-173](SPEC.md#L172-L173)** — task 6 specifies a yfinance capability declaring
"US strong, TASE prices only / sparse fundamentals", but the shipped declaration grants all 20
metrics to both markets, with sparseness noted only in a comment
([yfinance/capability.py:4-7](src/financial_charts/sources/yfinance/capability.py#L4-L7)).
Either amend the SPEC to record the decision that per-ticker sparseness is handled by the
adapter's per-metric availability flags rather than by the market-level declaration, or open a
task to narrow the declaration. **This one is a design question, not a typo — decide it before
editing either side.**

3.7 **[SPEC.md:67](SPEC.md#L67)** — `config.py` is described as holding "DATA_SOURCE, API keys,
defaults", but it holds no API keys; `TWELVEDATA_API_KEY` is read directly at
[twelvedata/adapter.py:51](src/financial_charts/sources/twelvedata/adapter.py#L51). Change the
description to "env config: DATA_SOURCE + render defaults; loads `.env` (each adapter reads its
own credentials)".

3.8 **[SPEC.md:192-193](SPEC.md#L192-L193)** — task 15's hook values are written as bare commands;
the shipped hooks use venv-absolute paths (`$CLAUDE_PROJECT_DIR/.venv/bin/pytest -q`). Update the
task text to match what was actually wired.

### Priority 4 — Undocumented dependencies

4.1 **[SPEC.md:156-158](SPEC.md#L156-L158)** — add `flask` to the dependency list; it is a
runtime dependency ([pyproject.toml:10](pyproject.toml#L10)) that no design doc mentions.

4.2 **[SPEC.md:156-158](SPEC.md#L156-L158)** — add a note that Plotly.js is a **CDN asset, not a
Python package** (pinned at [index.html:139](src/financial_charts/web/templates/index.html#L139)),
so a reader auditing `pyproject.toml` for the charting stack doesn't conclude it's missing.

4.3 **[README.md:12](README.md#L12)** — note that the web UI requires network access to
`cdn.plot.ly` at page load. The dashboard silently renders nothing useful offline; nothing
currently warns a user.

### Priority 5 — Stale references carried over from previous reports

Not applicable — this is the baseline report. Populate this section in the next audit.

### Priority 6 — Test coverage expansion targets (ranked by value)

6.1 **`sources/currency.py` — highest value.** `map_currency` is the one place the agorot→ILS
decision is made, and the agorot/millions trap is the project's stated core risk
([CLAUDE.md:119-121](CLAUDE.md#L119-L121)). A `currency_test.py` should pin: `"ILA"` → `ILS`,
`"USD"` → `USD`, `"ILS"` → `ILS`, and that an unknown code and `None` both return `None` (so the
caller degrades to "no data" rather than guessing).

6.2 **Range-boundary constants.** [ranges.py:11](src/financial_charts/sources/ranges.py#L11)
rounds `"6m"` up to 1 year and [ranges.py:16](src/financial_charts/sources/ranges.py#L16) uses
`10_000` as the `"max"` sentinel. `ranges_test.py` has 6 tests; confirm both of these specific
values are pinned, since capability validation depends on them.

6.3 **Default chart-set membership.** Already pinned by
`registry_test.py::test_builtin_fundamentals_set_has_six_charts`
([registry.py:14](src/financial_charts/charts/registry.py#L14)) — good. Consider the mirror
assertion on the catalog: a test pinning `len(available_charts()) == 21` would have caught a
silent inventory change, and would keep [PROGRESS.md:75](PROGRESS.md#L75)'s count honest.

6.4 **The two `capability.py` declarations** (findings 6.2, 6.3) are low-risk pure data and are
covered indirectly. No dedicated tests recommended.
