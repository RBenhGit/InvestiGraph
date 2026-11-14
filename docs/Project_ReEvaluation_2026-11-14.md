# Project Re-Evaluation — InvestiGraph

**Date:** 2026-11-14
**Focus:** Full Project
**Previous Reports:** 2026-08-29 (Full Project) and 2026-08-29b (second pass, targeted follow-up). Both are folded into the "Comparison with Previous Reports" section below and deleted by this run, so this is the only report left.

## Executive Summary

The docs are in better shape than at the last audit. All six open items from the 2026-08-29 reports are resolved. README now lists `GET /`, `GET /render` and `POST /chart-sets`, documents the `valuate` flags, and states the Rule #1 CLI defaults. The "Merge complete" section of PROGRESS.md was rewritten to match the finished merge. PROGRESS.md's last recorded test count (639 pytest + 124 vitest) matches what I ran today: 639 passed, 124 passed, ruff clean. CLAUDE.md's Gotchas all still match the code, including the TASE unit-mix repair, the axis-currency label, and the agorot division in `/api/live-prices`.

The code has moved on since August in three ways, and README did not follow:

1. **Per-chart period/range, trend fits and a 3-column grid** were merged (`feat/per-chart-config`). The global period and range pickers are gone from the web UI.
2. **The default data source flipped to `twelvedata`.** README line 30 still shows `DATA_SOURCE=yfinance`.
3. **Peter Lynch was removed and server-side evaluators added.** The evaluators are documented; the Lynch removal left no README residue.

**Highest-impact gap:** README line 30 tells a new user to set `DATA_SOURCE=yfinance`, but the code default and `.env.example` are `twelvedata`. A user who follows `.env.example` without a Twelve Data key gets a credentials error. Right behind it, README's CLI synopsis presents `--period`/`--range` as the way to pick a timeframe. In reality each chart declares its own period and range, and the flags are now optional overrides.

---

## Findings

### 1. Documentation Accuracy

| # | Doc claim | Doc location | Code reality | Code location | Status |
|---|---|---|---|---|---|
| 1.1 | `DATA_SOURCE=yfinance        # or twelvedata` shown as the example `.env` | [README.md:30](../README.md#L30) | Default is `"twelvedata"`; `.env.example` also says `twelvedata` | [config.py:12](../src/investigraph/config.py#L12), [.env.example:5](../.env.example#L5) | **Mismatch** |
| 1.2 | "chosen by `DATA_SOURCE`" with no default stated | [README.md:132](../README.md#L132) | Default is `twelvedata` (paid, needs key) | [config.py:12](../src/investigraph/config.py#L12) | **Incomplete** |
| 1.3 | CLI synopsis `[--period quarterly\|ttm\|annual] [--range 6m\|...\|max]` with no hint that they are overrides | [README.md:66](../README.md#L66) | Both default to `None`: "override every chart's own period/range ... omit to let each chart use its declared" | [__main__.py:54-72](../src/investigraph/__main__.py#L54-L72) | **Incomplete** |
| 1.4 | Web UI description: "Enter a ticker once: the chart grid ... render from the same fetch" | [README.md:45-46](../README.md#L45-L46) | Each chart declares `(period, range)`; one fetch per distinct pair. Global pickers removed. | [app.py:69-145](../src/investigraph/web/app.py#L69-L145), [PROGRESS.md:473-479](../PROGRESS.md#L473-L479) | **Incomplete** |
| 1.5 | Default `fundamentals` set = 6 charts; catalog = 21 | [README.md:92](../README.md#L92) | 6 in the set, 21 in `_CHARTS` | [registry.py:16-23](../src/investigraph/charts/registry.py#L16-L23), [catalog.py:28-49](../src/investigraph/charts/catalog.py#L28-L49) | Match |
| 1.6 | Ticker regex `^[A-Za-z0-9.\-]+$` | [README.md:94](../README.md#L94) | Exact | [market.py:5](../src/investigraph/sources/market.py#L5) | Match |
| 1.7 | Growth chain `analyst_estimate_5y → historical_3y → historical_1y → None`, one function, both entry points | [CLAUDE.md:88-93](../CLAUDE.md#L88-L93) | `resolve_growth_rate_percent`, called from `valuate_service.py:129`, shared by the CLI's `handle_valuate` | [growth.py:102](../src/investigraph/valuation/growth.py#L102), [valuate_service.py:129](../src/investigraph/web/valuate_service.py#L129) | Match |
| 1.8 | `Money.to()` / `require_same_currency()` guard agorot vs shekel-millions | [CLAUDE.md:75-78](../CLAUDE.md#L75-L78) | Both exist | [models.py:51](../src/investigraph/template/models.py#L51), [models.py:58](../src/investigraph/template/models.py#L58) | Match |
| 1.9 | Live TASE quote in agorot, `/api/live-prices` divides by 100 | [CLAUDE.md:78-80](../CLAUDE.md#L78-L80) | `last_price / 100 if quote_currency == AGOROT_CODE` | [app.py:374](../src/investigraph/web/app.py#L374) | Match |
| 1.10 | `_fix_unit_mixups` rescales a bar 70-150x off its neighbours' median | [CLAUDE.md:81-85](../CLAUDE.md#L81-L85) | `_UNIT_MIXUP_RATIO = (70, 150)` | [twelvedata/adapter.py:302-305](../src/investigraph/sources/twelvedata/adapter.py#L302-L305) | Match |
| 1.11 | Axis label uses `currency_label`, not `currency_symbol` | [CLAUDE.md:85-87](../CLAUDE.md#L85-L87) | Both defined in `charts/base.py` | [base.py:73](../src/investigraph/charts/base.py#L73), [base.py:80](../src/investigraph/charts/base.py#L80) | Match |
| 1.12 | `sources/fx_rate/` supplies spot rate and per-date series | [CLAUDE.md:80-81](../CLAUDE.md#L80-L81), [README.md:145-147](../README.md#L145-L147) | `attach_fx_series` + spot helpers | [fx_rate/adapter.py:68](../src/investigraph/sources/fx_rate/adapter.py#L68) | Match |
| 1.13 | NaN gap-marker must use `_nan_like`; call sites gated by `mark_gaps` | [CLAUDE.md:94-103](../CLAUDE.md#L94-L103) | `_nan_like` defined; `mark_gaps=True` at the TTM call sites | [trailing.py:38](../src/investigraph/template/trailing.py#L38), [trailing.py:340, 353](../src/investigraph/template/trailing.py#L340) | Match |
| 1.14 | TTM composed from cached QUARTERLY + ANNUAL series in `sources/ttm.py` | [README.md:88-91](../README.md#L88-L91) | `sources/ttm.py` exists, has a colocated test; `__main__.py` imports `build_ttm_fundamentals` | [ttm.py](../src/investigraph/sources/ttm.py), [__main__.py:35](../src/investigraph/__main__.py#L35) | Match |
| 1.15 | `scripts/test.sh` runs pytest + vitest; CLAUDE.md lists bare `npx vitest run` as part of it | [CLAUDE.md:6](../CLAUDE.md#L6) | Bare `npx vitest run` on this machine's default Node 18 crashes (`styleText` missing). `scripts/test.sh` switches to Node 22 itself. Passes under Node 22 (124/124). | [scripts/test.sh:19-27](../scripts/test.sh#L19-L27) | Match (the `scripts/test.sh` path works; see Recommendation 2.1) |

### 2. Undocumented Code

| # | Item | Code location | Doc coverage | Status |
|---|---|---|---|---|
| 2.1 | Per-chart `(period, range)` declared on `Chart`; global pickers removed | [app.py:69-145](../src/investigraph/web/app.py#L69-L145) | PROGRESS.md only; absent from README | **Missing** |
| 2.2 | Trend-fit overlay (linear/exponential) on Revenue, Net Income, EPS, FCF | [charts/fit.py](../src/investigraph/charts/fit.py) | PROGRESS.md only; absent from README | **Missing** |
| 2.3 | 3-column chart grid | `web/static/style.css`, `web/templates/index.html` | PROGRESS.md only | **Missing** (minor) |
| 2.4 | `web/static/about.html` (methodology page) | [web/static/about.html](../src/investigraph/web/static/about.html) | Mentioned only in PROGRESS.md (:372, :378); README does not link it | **Missing** (minor) |
| 2.5 | `valuate` flags `-s/-m/-n/-H`, Rule #1 CLI defaults (15 / 15% / 10y) | [__main__.py:452-454](../src/investigraph/__main__.py#L452-L454), [:458-490](../src/investigraph/__main__.py#L458-L490) | [README.md:103-108](../README.md#L103-L108) | **Resolved** (was open since 08-29) |
| 2.6 | `GET /`, `GET /render`, `POST /chart-sets` | [app.py:164](../src/investigraph/web/app.py#L164), [:210](../src/investigraph/web/app.py#L210), [:248](../src/investigraph/web/app.py#L248) | [README.md:51-55](../README.md#L51-L55) | **Resolved** (was open since 08-29) |
| 2.7 | `GET/POST /api/evaluators`, `DELETE /api/evaluators/<name>`, `PUT /api/evaluators/selected` | [app.py:378-402](../src/investigraph/web/app.py#L378-L402) | [README.md:49-51](../README.md#L49-L51) | Match |
| 2.8 | `.claude/hooks/*`, `.claude/agents/*` | `.claude/` | README: "hooks auto-format/lint edited files and gate turns on a green test suite" ([README.md:168-169](../README.md#L168-L169)); `post-edit.sh` and `stop-test-gate.sh` exist | Match |

### 3. Dead References

| # | Doc reference | Doc location | Present in code? | Status |
|---|---|---|---|---|
| 3.1 | `merge/import-sources` branch, "not yet merged to main" | [PROGRESS.md:17](../PROGRESS.md#L17) | Branch deleted (only `main` exists locally and on `origin`). Inside the Phase 2 entry, a point-in-time record. | Stale, acceptable (historical) |
| 3.2 | `git log` instruction for `merge/import-sources` | [PROGRESS.md:146-149](../PROGRESS.md#L146-L149) | Now reads "...was fast-forward merged into `main` and deleted after Phase 9", and gives a SHA range | **Resolved** |
| 3.3 | "Merge complete" section | [PROGRESS.md:281-286](../PROGRESS.md#L281-L286) | Rewritten to state the completed fast-forward merge and deletion | **Resolved** |
| 3.4 | Lynch method (`valuation/lynch/`, `lynch_fair_value`, "Method A/B") | README.md, CLAUDE.md: none. PROGRESS.md, MERGE_SPEC.md: historical entries only | Deleted from code on 2026-08-29; the deleted-module references are deliberately kept in the historical logs ([PROGRESS.md:358-361](../PROGRESS.md#L358-L361)) | Match (no live doc references) |
| 3.5 | `GET /render` described as unused by the shipped UI | [README.md:52-54](../README.md#L52-L54) | Still true: no `/render` reference in `app.js` or `index.html` | Match |
| 3.6 | `TODO.md` | Removed in commit 8681537 | No remaining references to it found in README/CLAUDE.md/PROGRESS.md | Match |
| 3.7 | `docs/UX_NOTES.md` (8-line wish-list: 3-column grid, default source = twelvedata, drop global time frame) | [PROGRESS.md:473-479](../PROGRESS.md#L473-L479) cites it as the source for the per-chart-config work | All three items are implemented. The file is a stale to-do list. | **Stale** (see Recommendation 3.2) |

### 4. Configuration Alignment

| # | Env var | `.env.example` | Read by code at | Documented at | Status |
|---|---|---|---|---|---|
| 4.1 | `DATA_SOURCE` | Yes (`twelvedata`) | [config.py:12](../src/investigraph/config.py#L12) (default `twelvedata`) | [README.md:30](../README.md#L30) says `yfinance` | **Mismatch** (see 1.1) |
| 4.2 | `TWELVEDATA_API_KEY` | Yes | [twelvedata/adapter.py:65](../src/investigraph/sources/twelvedata/adapter.py#L65) | [README.md:31](../README.md#L31) | Match |
| 4.3 | `HISTORY_FILE_PATH` | Yes (commented, optional) | [history/store.py:72](../src/investigraph/history/store.py#L72) | [README.md:141-144](../README.md#L141-L144) | Match |
| 4.4 | Any other `os.environ`/`getenv` in `src/` | — | None (grep over non-test `.py`) | — | Match |

I did not read `.env` (it holds real credentials). Only `.env.example` was compared.

### 5. Constants & Weights Verification

| # | Constant / formula | Documented as | Doc location | Coded as | Code location | Status |
|---|---|---|---|---|---|---|
| 5.1 | Ticker regex | `^[A-Za-z0-9.\-]+$` | [README.md:94](../README.md#L94) | Same | [market.py:5](../src/investigraph/sources/market.py#L5) | Match |
| 5.2 | Default chart set / catalog size | 6 / 21 | [README.md:92](../README.md#L92) | 6 / 21 | [registry.py:16](../src/investigraph/charts/registry.py#L16), [catalog.py:28](../src/investigraph/charts/catalog.py#L28) | Match |
| 5.3 | Unit-mix rescale window | 70-150x | [CLAUDE.md:84](../CLAUDE.md#L84) | `(70, 150)` | [twelvedata/adapter.py:302](../src/investigraph/sources/twelvedata/adapter.py#L302) | Match |
| 5.4 | Rule #1 CLI defaults | exit P/E 15, 15% required return, 10y | [README.md:106-108](../README.md#L106-L108) | `15`, `15`, `10` | [__main__.py:452-454](../src/investigraph/__main__.py#L452-L454) | Match (was Missing) |
| 5.5 | TTM gap threshold | not documented (internal) | — | `_MAX_QUARTER_WINDOW_DAYS = 330` | [trailing.py:35](../src/investigraph/template/trailing.py#L35) | Match (internal-only, as intended) |
| 5.6 | SMA windows | not documented | — | `(50, 150, 200)` | [price.py:7](../src/investigraph/charts/builtins/price.py#L7) | Missing (low value, an implementation detail; carried unchanged) |
| 5.7 | Default CLI/web range | not documented | — | `DEFAULT_RANGE = "5y"` | [config.py:7](../src/investigraph/config.py#L7) | Missing (minor; now only a fallback, since charts declare their own range) |
| 5.8 | Default `--range` for `commission-source` / `verify-source` | not documented | — | `"max"` / `"5y"` | [__main__.py:406](../src/investigraph/__main__.py#L406), [:287](../src/investigraph/__main__.py#L287) | Missing (minor) |

### 6. Test Coverage

**639 pytest tests collected and passing** (`uv run pytest -q` → `639 passed in 10.92s`) across **65 test files**, plus **124 vitest tests** in 2 files (`app.test.js`, `valuations.test.js`; `124 passed` under Node 22). `ruff check` → "All checks passed!". PROGRESS.md's last recorded figures (:588-589, "639 pytest + 124 vitest") agree exactly.

#### Per-file breakdown (top 22 by count)

| Test file | Tests |
|---|---|
| [template/trailing_test.py](../src/investigraph/template/trailing_test.py) | 55 |
| [__main___test.py](../src/investigraph/__main___test.py) | 42 |
| [web/app_test.py](../src/investigraph/web/app_test.py) | 36 |
| [history/evaluators_test.py](../src/investigraph/history/evaluators_test.py) | 30 |
| [web/chart_data_test.py](../src/investigraph/web/chart_data_test.py) | 29 |
| [history/store_test.py](../src/investigraph/history/store_test.py) | 26 |
| [web/valuate_route_test.py](../src/investigraph/web/valuate_route_test.py) | 24 |
| [valuation/growth_test.py](../src/investigraph/valuation/growth_test.py) | 24 |
| [sources/twelvedata/adapter_test.py](../src/investigraph/sources/twelvedata/adapter_test.py) | 19 |
| [valuation/rule_one/calculate_test.py](../src/investigraph/valuation/rule_one/calculate_test.py) | 16 |
| [valuation/resolve_eps_test.py](../src/investigraph/valuation/resolve_eps_test.py) | 16 |
| [template/derived_test.py](../src/investigraph/template/derived_test.py) | 16 |
| [sources/commission_test.py](../src/investigraph/sources/commission_test.py) | 16 |
| [web/evaluators_route_test.py](../src/investigraph/web/evaluators_route_test.py) | 14 |
| [sources/fx_rate/adapter_test.py](../src/investigraph/sources/fx_rate/adapter_test.py) | 13 |
| [sources/verify_test.py](../src/investigraph/sources/verify_test.py) | 11 |
| [charts/fit_test.py](../src/investigraph/charts/fit_test.py) | 11 |
| [charts/base_test.py](../src/investigraph/charts/base_test.py) | 11 |
| [web/service_test.py](../src/investigraph/web/service_test.py) | 10 |
| [template/models_test.py](../src/investigraph/template/models_test.py) | 10 |
| [valuation/historical_pe_test.py](../src/investigraph/valuation/historical_pe_test.py) | 9 |
| [sources/yfinance/adapter_test.py](../src/investigraph/sources/yfinance/adapter_test.py) | 9 |
| ... (43 more files, 1-9 tests each) | — |
| **Total** | **639** |

#### Coverage gaps (non-`__init__` modules with no colocated `*_test.py`)

| # | Module | Assessment |
|---|---|---|
| 6.1 | [web/valuate_service.py](../src/investigraph/web/valuate_service.py) | Low risk. Exercised end to end by `valuate_route_test.py` (24) and `__main___test.py`. Unchanged from 08-29. |
| 6.2 | [web/history_service.py](../src/investigraph/web/history_service.py) | Low risk. Covered by `history_route_test.py` and the CLI history tests. Unchanged. |
| 6.3 | [sources/twelvedata/capability.py](../src/investigraph/sources/twelvedata/capability.py), [sources/yfinance/capability.py](../src/investigraph/sources/yfinance/capability.py) | Low risk. Pure declarations, tested indirectly. Unchanged. |
| 6.4 | [history/models.py](../src/investigraph/history/models.py), [sources/yahoo_consensus/models.py](../src/investigraph/sources/yahoo_consensus/models.py), [valuation/shared/types.py](../src/investigraph/valuation/shared/types.py) | Low risk. Pure models. Unchanged. |
| 6.5 | [charts/builtins/_test_helpers.py](../src/investigraph/charts/builtins/_test_helpers.py) | Not a gap. It is a test helper. |

New modules since 08-29 (`history/evaluators.py`, `charts/fit.py`, `sources/ttm.py`, `web/chart_set_store.py`) all have colocated tests. The gap list is the same as before; nothing new has been added to it.

---

## Comparison with Previous Reports

### Since 2026-08-29 and 2026-08-29b Reports

| Prior finding | Current status |
|---|---|
| 08-29 §1.1 / 08-29b §1.1: test count out of date (500 vs 503, later 507) | **Resolved**. PROGRESS.md records 639 pytest + 124 vitest; live run is 639 / 124. The figure has moved on since both reports (503/507 → 639) and is in sync again. |
| 08-29 §1.2-1.10 (growth chain, `Money` guards, chart-set counts, valuation panel forced `Period.ANNUAL`, ticker regex, `/static/valuations.html`, env vars, TTM derivation, historical-doc framing) | **Resolved/Match** (re-checked: chain, `Money`, counts, regex, TTM). One claim changed: the valuation panel's forced `Period.ANNUAL` is a PROGRESS.md-only design record and was not re-derived this pass. The env-var row is now a Mismatch on the default value (1.1), because the default flipped. |
| 08-29b §1.11-1.12 (`_nan_like` Gotcha, README TTM gap-breaking sentence) | **Resolved/Match** (rows 1.13 and 1.14). |
| 08-29b §1.13 / §3.3 (PROGRESS.md "Merge complete" false current-state claim) | **Resolved**. Rewritten at [PROGRESS.md:281-286](../PROGRESS.md#L281-L286). |
| 08-29b §3.2 (`git log merge/import-sources` instruction at PROGRESS.md:147) | **Resolved**. Now points at a SHA range and says the branch was deleted. |
| 08-29b §3.1 (PROGRESS.md:17 "not yet merged to main") | **Still unfixed, accepted**. It sits inside a Phase 2 point-in-time entry; I leave it as historical. |
| 08-29 §2.1-2.3 (`GET /`, `GET /render`, `POST /chart-sets` undocumented) | **Resolved** at [README.md:51-55](../README.md#L51-L55). |
| 08-29 §2.4-2.5 / §5.5 (`valuate` flags, Rule #1 CLI defaults undocumented) | **Resolved** at [README.md:103-108](../README.md#L103-L108). |
| 08-29 §2.6 / §6.1-6.2 (`valuate_service.py`, `history_service.py` untested) | **Still unfixed, accepted** (low risk; same assessment). |
| 08-29 §5.1 (SMA windows undocumented) | **Still unfixed, accepted** (implementation detail). |
| 08-29 Priority 6.1 (route-doc-lint test walking `app.url_map`) | **Not done**. README now covers every route by hand (the manual check I made this pass), but nothing enforces it. Still a reasonable future target. |
| 08-29 Priority 3 (PROGRESS.md entry for the NaN fix) | **Satisfied** (as of 08-29b). |

New this pass (not in either prior report): 1.1-1.4 and 2.1-2.4 (changes since 08-29 that README did not absorb) and 3.7 (stale `docs/UX_NOTES.md`).

---

## Recommendations

### Priority 1 — User-facing docs (`README.md`)

1.1 **[README.md:30](../README.md#L30)** — change `DATA_SOURCE=yfinance        # or twelvedata; overridable per render with --source` to `DATA_SOURCE=twelvedata      # default; or yfinance (free, no key); overridable per render with --source`. Change line 31's comment to `# required with twelvedata, the default`. Line 34 ("`yfinance` needs no key") is correct as written and can stay.

1.2 **[README.md:132](../README.md#L132)** — change "chosen by `DATA_SOURCE`" to "chosen by `DATA_SOURCE` (default `twelvedata`)".

1.3 **[README.md:45-46](../README.md#L45-L46)** — after "...render from the same fetch." add: "Each chart declares its own period (quarterly / TTM / annual) and range, so one page can mix, say, a TTM EPS chart with a 10-year annual revenue chart; Revenue, Net Income, EPS and Free Cash Flow also have a toggleable linear/exponential trend-fit overlay with the fitted growth rate. Charts lay out three to a row. Methodology is on `/static/about.html`."

1.4 **[README.md:66-67](../README.md#L66-L67)** — after the synopsis add: "`--period` and `--range` are optional overrides; omitted, each chart uses its own declared period and range."

### Priority 2 — Internal/developer docs (`CLAUDE.md`)

2.1 **[CLAUDE.md:6](../CLAUDE.md#L6)** — this is the only item here, and it is optional. Say that `npx vitest run` alone needs Node ≥22.22.2 and that `scripts/test.sh` selects it. As written, copying the vitest half on its own fails on this machine's default Node 18 with a `styleText` import error. Suggested wording: "`scripts/test.sh` (runs `uv run pytest -q` plus vitest under Node ≥22.22.2, which it selects itself; bare `npx vitest run` needs that Node on PATH)." The Gotchas section needs no changes; every check passed.

### Priority 3 — Other project docs

3.1 **[PROGRESS.md:17](../PROGRESS.md#L17)** — optional. Leave as is (historical).

3.2 **[docs/UX_NOTES.md](../docs/UX_NOTES.md)** — all three requests it records are implemented ([PROGRESS.md:473-479](../PROGRESS.md#L473-L479)). Either delete it, which matches the recent "remove TODO.md" cleanup, or prefix it with "Status: all items implemented 2026-11-14 (see PROGRESS.md)". PROGRESS.md:475 cites it as the origin of the work, so a status header is the safer minimal change. The file also has typos ("Chrts", "availible"), which I'd leave alone as part of the historical record.

3.3 **[docs/financial_charts_progress.md](../docs/financial_charts_progress.md)** and **[docs/SPEC.md](../docs/SPEC.md)** — no change. Both are pre-merge historical records, and README/PROGRESS.md frame them that way.

### Priority 4 — Undocumented dependencies

None found. No `import` in `src/` lacks a `pyproject.toml` entry that I could see, and the only env vars read are the three documented ones. (I did not audit `pyproject.toml` line by line this pass; no dependency changes appear in the recent git log.)

### Priority 5 — Stale references carried over from previous reports

None needing action. The only carried item is PROGRESS.md:17 (accepted as historical, see 3.1 above).

### Priority 6 — Test coverage expansion targets (ranked by value)

6.1 **Route-doc lint** (carried from 08-29 Priority 6.1). A test that walks `app.url_map` and fails when a route path is not mentioned in `README.md`. README gained three routes by hand this cycle, so the manual process works, but a check would protect it. Medium value.

6.2 **Default-source consistency check.** A small test asserting that `config.data_source_name()`'s default, `.env.example`'s `DATA_SOURCE` line and README's example agree would have caught finding 1.1. Low cost, since `config_test.py` already exists.

6.3 No other gaps are worth filling. The remaining untested modules are the same low-risk service wrappers, declarations and pure models as before.
