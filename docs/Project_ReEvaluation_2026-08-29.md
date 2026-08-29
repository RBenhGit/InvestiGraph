# Project Re-Evaluation — InvestiGraph

**Date:** 2026-08-29
**Focus:** Full Project
**Previous Reports:** 2026-08-02, Full Project — pre-merge, audited the standalone `financial_charts` module before the Eps_Evaluation merge. (Superseded by this report and removed; its findings are folded into the "Comparison with Previous Reports" section below.)

## Executive Summary

The project has been transformed since the last audit: a 9-phase merge folded Eps_Evaluation's
valuation engine, history store, and front end into what was Financial_Charts, producing
InvestiGraph — a renamed package (`src/investigraph/`), a unified web app, and 503 backend +
105 front-end tests (up from 288). The core docs (`README.md`, `CLAUDE.md`, `PROGRESS.md`,
`docs/MERGE_SPEC.md`) are in excellent shape: every major claim checked — the growth-fallback
chain being one shared function ([growth.py:102-118](src/investigraph/valuation/growth.py#L102-L118),
called identically from [valuate_service.py:118-122](src/investigraph/web/valuate_service.py#L118-L122)
and [__main__.py:599](src/investigraph/__main__.py#L599)), the `Money` currency/scale guards, the
6-of-21 chart-set split, the ticker charset regex, the `/static/valuations.html` path, and the
valuation panel's forced `Period.ANNUAL` fetch — matches code exactly. All ten of the previous
report's Priority 1–4 findings are resolved; every dead reference and mismatch it flagged in the
old README/CLAUDE.md is gone, replaced by an accurate rewrite. `docs/SPEC.md` and
`docs/financial_charts_progress.md` are the previous report's subject matter, now explicitly
labeled historical artifacts of the pre-merge tool and correctly excluded from the current docs'
authority — this is by design, not drift.

The **highest-impact gap** is new and much smaller in scope than last time: three Flask routes
exist in code with no doc coverage at all — `GET /` (the main picker page),
`GET /render` (a server-rendered HTML path with no front-end caller left —
[app.py:200-205](src/investigraph/web/app.py#L200-L205)), and
`POST /chart-sets` (saves a custom chart set from the checkbox picker —
[app.py:226](src/investigraph/web/app.py#L226)) — while README's endpoint list only covers the six
JSON API routes. The CLI's `valuate` subcommand has the same shape of gap: its four real flags
(`--save`, `--mos`, `--notes`, `--history`) and its hardcoded Rule #1 defaults (exit P/E 15,
required return 15%, 10 years — [__main__.py:395-400](src/investigraph/__main__.py#L395-L400)) are
invisible in README, which shows only the bare `valuate AAPL` form.

Secondary: the test count in `PROGRESS.md` (500 pytest) is one commit behind the actual working
tree (503 pytest, from an uncommitted in-progress fix session for a known interpolation gap —
this is normal mid-flight state, not drift, and should self-resolve at the next commit + PROGRESS
update).

---

## Findings

### 1. Documentation Accuracy

| # | Doc claim | Doc location | Code reality | Code location | Status |
|---|---|---|---|---|---|
| 1.1 | "500 pytest + 105 vitest passing" (last recorded figure) | [PROGRESS.md:316](PROGRESS.md#L316) | 503 pytest + 105 vitest collected | `pytest --collect-only -q`, `scripts/test.sh` | **Mismatch** (see note below) |
| 1.2 | Growth chain: `analyst_estimate_5y → historical_3y → historical_1y → None`, one function, both entry points | [CLAUDE.md:79-84](CLAUDE.md#L79-L84) | Exact order at `resolve_growth_rate_percent` | [growth.py:102-118](src/investigraph/valuation/growth.py#L102-L118); called from [valuate_service.py:118-122](src/investigraph/web/valuate_service.py#L118-L122) and [__main__.py:599](src/investigraph/__main__.py#L599) via the same `handle_valuate` | Match |
| 1.3 | `Money.to()` / `require_same_currency()` prevent silently combining agorot and shekel-millions | [CLAUDE.md:75-78](CLAUDE.md#L75-L78) | Both exist as described, raising `ValueError` on mismatch | [models.py:51-56](src/investigraph/template/models.py#L51-L56), [models.py:58-68](src/investigraph/template/models.py#L58-L68) | Match |
| 1.4 | Default `fundamentals` chart set = 6 charts; catalog = 21 | [README.md:74](README.md#L74) | 6 in registry, 21 in catalog | [registry.py:16-23](src/investigraph/charts/registry.py#L16-L23), [catalog.py:27-48](src/investigraph/charts/catalog.py#L27-L48) | Match |
| 1.5 | Valuation panel always fetches `Period.ANNUAL`, independent of chart-grid period | [PROGRESS.md:122-131](PROGRESS.md#L122-L131) (design decision recorded at Phase 6 convergence review) | Hardcoded `Period.ANNUAL` in `_load_fundamentals_or_raise` | [valuate_service.py:216-218](src/investigraph/web/valuate_service.py#L216-L218) | Match |
| 1.6 | Tickers matched by `^[A-Za-z0-9.\-]+$`, no exchange-qualified form | [README.md:76-77](README.md#L76-L77) | Exact regex | [market.py:5](src/investigraph/sources/market.py#L5) | Match |
| 1.7 | Saved valuations appear at `/static/valuations.html` | [README.md:47](README.md#L47) | File served at that path via Flask's default static route; no override | [web/static/valuations.html](src/investigraph/web/static/valuations.html), [app.py](src/investigraph/web/app.py) (no custom `/valuations.html` route) | Match |
| 1.8 | Env vars: `TWELVEDATA_API_KEY`, `DATA_SOURCE`, `HISTORY_FILE_PATH` | [README.md:27-32](README.md#L27-L32), [.env.example](.env.example) | Exactly these three read in code, no more, no less | [config.py:13](src/investigraph/config.py#L13), [twelvedata/adapter.py:52](src/investigraph/sources/twelvedata/adapter.py#L52), [history/store.py:72](src/investigraph/history/store.py#L72) | Match |
| 1.9 | `--period ttm` is derived by summing trailing quarters, not natively fetched | [README.md:62-77](README.md#L62-L77) | Matches `derive_ttm_fundamentals` in both adapters | [trailing.py](src/investigraph/template/trailing.py), [PROGRESS.md:289-316](PROGRESS.md#L289-L316) | Match |
| 1.10 | `docs/SPEC.md` / `docs/financial_charts_progress.md` describe `financial_charts` module, pre-merge | Files themselves | Both are correctly framed by README/PROGRESS as historical, not current-state docs | [README.md:10](README.md#L10), [PROGRESS.md:29-31](PROGRESS.md#L29-L31) | Match (intentional, not drift) |

**Note on 1.1:** the 503-vs-500 gap is three tests added in an *uncommitted* working-tree fix
(`git status` shows `template/derived.py`, `template/trailing.py`, and their tests modified but
not committed) for a known issue already tracked in
[.claude/agent-memory/code-reviewer/skipped-points-interpolate-across-gaps.md](.claude/agent-memory/code-reviewer/skipped-points-interpolate-across-gaps.md).
This isn't stale documentation so much as documentation one commit behind the working tree —
flagged for completeness, not as a defect, since `PROGRESS.md` is explicitly a per-completed-unit
log and this unit isn't committed yet.

### 2. Undocumented Code

| # | Item | Code location | Doc coverage | Status |
|---|---|---|---|---|
| 2.1 | `GET /` (main picker page) | [app.py:162-197](src/investigraph/web/app.py#L162-L197) | Absent from README's endpoint list ([README.md:48-49](README.md#L48-L49) lists only the 6 JSON API routes) | **Missing** |
| 2.2 | `GET /render` (server-rendered HTML dashboard) | [app.py:200-205](src/investigraph/web/app.py#L200-L205) | Absent from README; no front-end JS references this path anymore (superseded by client-side `/chart-data` + Plotly) | **Missing** — likely orphaned, see Recommendation 1.3 |
| 2.3 | `POST /chart-sets` (save a custom chart set) | [app.py:226-241](src/investigraph/web/app.py#L226-L241) | Absent from README; the checkbox-picker UI feature it backs is undocumented too | **Missing** |
| 2.4 | `valuate` subcommand flags: `-s/--save`, `-m/--mos`, `-n/--notes`, `-H/--history` | [__main__.py:404-437](src/investigraph/__main__.py#L404-L437) | README shows only bare `valuate AAPL` ([README.md:81-83](README.md#L81-L83)) | **Incomplete** |
| 2.5 | Rule #1 CLI defaults: exit P/E 15, required return 15%, 10 years | [__main__.py:395-400](src/investigraph/__main__.py#L395-L400) | Not stated anywhere a user would see them before running `valuate` | **Missing** |
| 2.6 | `web/history_service.py`, `web/valuate_service.py` — no colocated test file | [history_service.py](src/investigraph/web/history_service.py), [valuate_service.py](src/investigraph/web/valuate_service.py) | Exercised indirectly via [valuate_route_test.py](src/investigraph/web/valuate_route_test.py), [history_route_test.py](src/investigraph/web/history_route_test.py), and `__main___test.py` (CLI calls the same functions) | **Incomplete** (see §6) |

### 3. Dead References

| # | Doc reference | Doc location | Present in code? | Status |
|---|---|---|---|---|
| 3.1 | All Priority 1–4 items from the 2026-08-02 report (static-charts claims, missing `pyproject.toml`, stale cache-key doc, etc.) | prior report | All resolved — README/CLAUDE.md fully rewritten in Phase 9 | **Resolved** |
| 3.2 | `NotImplementedError`/`TODO`/`FIXME`/`XXX` markers anywhere in non-test source | — | None found (`grep -rn` over `src/investigraph/**/*.py` excluding tests) | Match (no dead markers) |
| 3.3 | `docs/SPEC.md`'s module layout, error types, `financial_charts` command names | [SPEC.md](docs/SPEC.md) | Superseded wholesale by the merge; correctly excluded from current-docs authority per README/PROGRESS framing | N/A — historical, not re-audited (see scope note in Recommendations) |

### 4. Configuration Alignment

| # | Env var | In `.env.example` | In `config.py` | Read by code at | Documented at | Status |
|---|---|---|---|---|---|---|
| 4.1 | `DATA_SOURCE` | Yes | Yes (default `"yfinance"`) | [config.py:13](src/investigraph/config.py#L13) | [README.md:30](README.md#L30) | Match |
| 4.2 | `TWELVEDATA_API_KEY` | Yes | No (read directly by adapter) | [twelvedata/adapter.py:52](src/investigraph/sources/twelvedata/adapter.py#L52) | [README.md:31](README.md#L31) | Match |
| 4.3 | `HISTORY_FILE_PATH` | Yes (commented out, optional) | No (read directly by store) | [history/store.py:72](src/investigraph/history/store.py#L72) | [README.md:117-119](README.md#L117-L119) | Match |
| 4.4 | No env var read anywhere outside these three sites | — | — | verified by grep over `src/investigraph/**/*.py` | — | Match (no undocumented vars, no documented-but-unused vars) |

### 5. Constants & Weights Verification

| # | Constant / formula | Documented as | Doc location | Coded as | Code location | Status |
|---|---|---|---|---|---|---|
| 5.1 | SMA windows | not restated in current docs (was in old SPEC.md) | — | `(50, 150, 200)` | [price.py:7](src/investigraph/charts/builtins/price.py#L7) | **Missing** (low value — implementation detail, not behavior a user configures) |
| 5.2 | yfinance / Twelve Data history depth (ANNUAL/QUARTERLY/TTM) | not stated in README/CLAUDE.md (README's Quick Start doesn't mention depth at all) | — | Corrected same-day (2026-08-29), after this report was first written: both files' QUARTERLY/TTM depths were stale, hand-written numbers never checked against live data. Live-verified via `commission-source`: yfinance ANNUAL=4y/QUARTERLY=1y/TTM=1y; Twelve Data (`pro` plan) ANNUAL=6y/QUARTERLY=1y/TTM=1y | [yfinance/capability.py](src/investigraph/sources/yfinance/capability.py), [twelvedata/capability.py](src/investigraph/sources/twelvedata/capability.py) | **Resolved** (was Missing; also see `commission.py`'s two bugs fixed the same day — TTM was structurally unprobeable and `max_history` used a `min`-over-every-metric that one sparse metric could zero out) |
| 5.3 | Ticker regex | `^[A-Za-z0-9.\-]+$` | [README.md:76-77](README.md#L76-L77) | Exact match | [market.py:5](src/investigraph/sources/market.py#L5) | Match |
| 5.4 | Growth-rate fallback chain order | `analyst_estimate_5y → historical_3y → historical_1y → None`, never defaults to 0 | [CLAUDE.md:79-84](CLAUDE.md#L79-L84) | Exact order; `None` surfaces as `MISSING_GROWTH_RATE`, never `0` | [growth.py:102-118](src/investigraph/valuation/growth.py#L102-L118) | Match |
| 5.5 | Rule #1 CLI defaults (exit P/E, required return, years) | not documented | — | `15`, `15`, `10` | [__main__.py:395-400](src/investigraph/__main__.py#L395-L400) | **Missing** |
| 5.6 | Default chart-set size vs. catalog size | "6 charts... catalog holds 21" | [README.md:74](README.md#L74) | 6 / 21 | [registry.py:16-23](src/investigraph/charts/registry.py#L16-L23), [catalog.py:27-48](src/investigraph/charts/catalog.py#L27-L48) | Match |
| 5.7 | `_MAX_QUARTER_WINDOW_DAYS` (TTM gap-detection threshold) | not documented externally (internal implementation detail, explained in its own docstring) | — | `330` | [trailing.py:35](src/investigraph/template/trailing.py#L35) | Match (appropriately internal-only) |

### 6. Test Coverage

**503 tests collected** across **57 test files** (`pytest --collect-only -q`), plus **105 vitest**
tests across 2 files — both suites green via `scripts/test.sh`.

#### Per-file breakdown (top 20 by count)

| Test file | Tests |
|---|---|
| [__main___test.py](src/investigraph/__main___test.py) | 38 |
| [web/app_test.py](src/investigraph/web/app_test.py) | 36 |
| [template/trailing_test.py](src/investigraph/template/trailing_test.py) | 35 |
| [history/store_test.py](src/investigraph/history/store_test.py) | 26 |
| [valuation/growth_test.py](src/investigraph/valuation/growth_test.py) | 24 |
| [web/valuate_route_test.py](src/investigraph/web/valuate_route_test.py) | 21 |
| [web/chart_data_test.py](src/investigraph/web/chart_data_test.py) | 18 |
| [valuation/rule_one/calculate_test.py](src/investigraph/valuation/rule_one/calculate_test.py) | 16 |
| [template/derived_test.py](src/investigraph/template/derived_test.py) | 16 |
| [sources/commission_test.py](src/investigraph/sources/commission_test.py) | 13 |
| [valuation/resolve_eps_test.py](src/investigraph/valuation/resolve_eps_test.py) | 11 |
| [sources/verify_test.py](src/investigraph/sources/verify_test.py) | 11 |
| [sources/twelvedata/adapter_test.py](src/investigraph/sources/twelvedata/adapter_test.py) | 11 |
| [template/models_test.py](src/investigraph/template/models_test.py) | 10 |
| [valuation/lynch/calculate_test.py](src/investigraph/valuation/lynch/calculate_test.py) | 9 |
| [sources/yahoo_consensus/adapter_test.py](src/investigraph/sources/yahoo_consensus/adapter_test.py) | 9 |
| [sources/registry_test.py](src/investigraph/sources/registry_test.py) | 9 |
| [web/history_route_test.py](src/investigraph/web/history_route_test.py) | 8 |
| [web/chart_set_store_test.py](src/investigraph/web/chart_set_store_test.py) | 8 |
| [valuation/historical_pe_test.py](src/investigraph/valuation/historical_pe_test.py) | 8 |
| ... (37 more files, 1–8 tests each) | — |
| **Total** | **503** |

#### Coverage gaps

| # | Module with no colocated test | Location | Assessment |
|---|---|---|---|
| 6.1 | `web/valuate_service.py` | [valuate_service.py](src/investigraph/web/valuate_service.py) | Low risk — exercised end-to-end via [valuate_route_test.py](src/investigraph/web/valuate_route_test.py) (21 tests, web path) and `__main___test.py` (CLI path), both calling the real `handle_valuate`. |
| 6.2 | `web/history_service.py` | [history_service.py](src/investigraph/web/history_service.py) | Same pattern — covered end-to-end by [history_route_test.py](src/investigraph/web/history_route_test.py) (8 tests, explicitly against the real store per that file's own docstring) plus CLI history tests. |
| 6.3 | `sources/twelvedata/capability.py`, `sources/yfinance/capability.py` | [twelvedata/capability.py](src/investigraph/sources/twelvedata/capability.py), [yfinance/capability.py](src/investigraph/sources/yfinance/capability.py) | Low risk — pure declarations, covered indirectly by validation/adapter tests (unchanged assessment from the 2026-08-02 report). |
| 6.4 | `history/models.py`, `sources/yahoo_consensus/models.py`, `valuation/shared/types.py` | — | Low risk — pure Pydantic/dataclass models exercised transitively by every test that constructs one. |

Every other non-`__init__`, non-declaration module has a colocated `*_test.py`. This is a stronger
position than the 2026-08-02 baseline, which flagged `sources/currency.py` as a real, high-value
gap (the agorot/ILS mapping); that gap is now closed — `sources/currency_test.py` exists with 5
tests.

---

## Comparison with Previous Reports

### Since 2026-08-02 Report

| Prior finding | Current status |
|---|---|
| 1.1–1.20 (README/CLAUDE.md described a static-charts, pre-web-UI-step-2 tool; stale cache key; stale `pyproject.toml` note) | **Resolved** — both files fully rewritten in Phase 9; every claim re-verified above matches current code. |
| 2.1–2.17 (undocumented CLI subcommands, `--charts` flag, `chart_support.py`, `catalog.py`, `derived.py`, `ranges.py`, `currency.py`, `commission.py`, `web/` package, `flask` dependency, `UnsupportedPeriod`) | **Resolved for the pre-merge scope** — README's Developer Commands section now documents `verify-source`, `capabilities`, `commission-source`; the `--charts` flag is in the CLI synopsis; the module list concern is moot since `docs/SPEC.md` (which had the stale layout) is now explicitly historical, not the living architecture doc — that role moved to README's Architecture section and CLAUDE.md, which don't attempt an exhaustive module list and so can't drift the same way. |
| 3.1–3.10 (iframe reference, static-PNG claim, hook command mismatch) | **Resolved** — the iframe and static-web-UI claims are gone from README; `docs/financial_charts_progress.md`'s internal self-contradiction (line 22-23 vs. line 55) is now framed by its own header as historical and superseded, defusing the contradiction rather than fixing the prose (an acceptable resolution for an archived file). |
| 4.1–4.3 (no `.env.example`; `DATA_SOURCE` documented-but-absent-from-.env; `config.py` description overstated) | **Resolved** — `.env.example` now exists and is accurate (finding 4.1–4.4 above); `config.py` is no longer separately documented as holding API keys anywhere in current docs. |
| 5.1–5.17 (constants mostly matched; a few undocumented internals like grid columns, DPI, range-sentinel values) | **Stale** — most of these constants lived in `dashboard/layout.py` and `sources/ranges.py`, both unchanged in shape; not re-verified in this pass since they weren't flagged as high-value and no doc claims about them exist to check for drift. The pattern repeats here with the new Rule #1 defaults (5.5) — low-stakes internal constants stay consistently undocumented across both audits, suggesting this project's norm is "document behavior, not tuning constants," which is a defensible, consistent choice rather than an oversight. |
| 6.1 (`sources/currency.py` untested — highest-value gap identified) | **Resolved** — `sources/currency_test.py` now exists with 5 tests. |
| 6.2–6.4 (capability.py declarations, index.html JS — low priority, no action recommended) | **Still unfixed / not applicable** — `capability.py` files remain untested directly (unchanged assessment, still low-risk); `index.html`'s JS is now covered by vitest (105 tests) added in Phase 8, which supersedes this concern entirely. |

---

## Recommendations

### Priority 1 — User-facing docs (`README.md`)

1.1 **[README.md:47-49](README.md#L47-L49)** — the Web UI section lists only the JSON API routes.
Add: "The picker page itself is served at `GET /`; a legacy server-rendered dashboard exists at
`GET /render` (no longer used by the current front end, which fetches `/chart-data` and renders
client-side); `POST /chart-sets` saves a custom chart set from the checkbox picker."

1.2 **[README.md:81-83](README.md#L81-L83)** — the `valuate` example shows only `valuate AAPL`.
Add a line: "`valuate TICKER [--save] [--mos PERCENT] [--notes TEXT] [--history [TICKER]]` —
`--save` persists the result, `--mos` sets Margin of Safety for Rule #1 (default 0), `--notes`
attaches free text to a saved record, `--history` lists saved valuations instead of computing a
new one (optionally filtered by ticker)."

1.3 **[README.md:83](README.md#L83)** (new sentence) — state the Rule #1 CLI defaults so a user
isn't surprised by the output: "Uses fixed Rule #1 assumptions of exit P/E 15, 15% required
return, and a 10-year horizon (`__main__.py`'s `_CLI_EXIT_PE_MULTIPLE`/
`_CLI_REQUIRED_RETURN_PERCENT`/`_CLI_YEARS`); these aren't currently configurable from the CLI."

### Priority 2 — Internal/developer docs (`CLAUDE.md`)

No changes recommended. CLAUDE.md's Gotchas, Commands, and Workflow sections all check out exactly
against current code; it deliberately doesn't attempt an exhaustive route/flag inventory (that's
README's job), so it isn't exposed to the Priority 1 gaps above.

### Priority 3 — Other project docs (`PROGRESS.md`)

3.1 **[PROGRESS.md](PROGRESS.md)** — once the current uncommitted `derived.resolve`/`ttm_series`
NaN-gap-marking fix (see finding 1.1) is committed, add its own Post-merge features entry (matching
the style of the existing "Derive `Period.TTM` by summing trailing quarters" entry) recording: the
fix, the updated test count (506, if no further tests are added), and a pointer to the now-updated
`.claude/agent-memory/code-reviewer/skipped-points-interpolate-across-gaps.md`. This isn't urgent —
it's normal mid-session state, not drift — but it's the next edit this file needs.

### Priority 4 — Undocumented dependencies

None found. `pyproject.toml`'s dependency list was not re-audited line-by-line in this pass (it
checked out clean in the 2026-08-02 report and no dependency-affecting doc claims have changed
since), but nothing in the code sweep above surfaced an import lacking a corresponding dependency
declaration.

### Priority 5 — Stale references carried over from previous reports that are still unfixed

None. Every item from the 2026-08-02 report's findings tables is either Resolved or explicitly
Stale-and-superseded (see the Comparison section above) — nothing from that report needs further
action.

### Priority 6 — Test coverage expansion targets (ranked by value)

6.1 **Route-level integration test asserting `GET /`, `GET /render`, and `POST /chart-sets` stay
documented.** Since these three routes were found undocumented by inspection rather than by a
failing check, consider a lightweight test (or a doc-lint script) that walks `app.url_map` and
fails if a route's path isn't mentioned anywhere in `README.md` — this is the kind of drift that
recurs silently as routes are added, and the previous report's Priority-1-fix cycle shows README
correctness doesn't stay durable without an explicit check tying the two together.

6.2 **No other coverage gaps rise to "recommended."** All modules flagged in §6 (`valuate_service.py`,
`history_service.py`, the two `capability.py` files, the three pure-model files) are already
exercised end-to-end by route/CLI tests or are low-risk pure data — consistent with the prior
report's own judgment calls on the same shape of gap (6.2–6.4 there), which held up over this
audit cycle.
