# Project Re-Evaluation Report
**Date:** 2026-08-28
**Focus:** Full Project
**Previous Reports:** 2026-08-22 (Full Project) — see "Comparison with Previous Reports" below.
An older 2026-08-16 audit exists only as the fully-resolved (`[x]` all 8 items) `TASKS.md`
punch-list and is not re-compared here.

## Executive Summary

39 commits landed between the 2026-08-22 report and today. The good news first: every one of
that report's 8 recommendations was genuinely acted on — the 3-scenario feature is now fully
documented in CLAUDE.md, the MoS dropdown is back to a single shared control matching the doc,
the `yahoo/types.ts` import exception is now spelled out explicitly, and both flagged
test-coverage gaps (`renderHistoryTable`'s legacy/scenario branching, a `base`/`bear`/`bull`
history round-trip test) now have dedicated tests. That's a clean sweep — CLAUDE.md was clearly
re-synced carefully at commit `bcaa962`.

The problem is everything shipped **after** that re-sync. In the following ~30 commits the
project built a substantial, unplanned-for-in-docs feature set — a per-evaluator history
subsystem (`data/evaluators/<name>.json`, legacy-file merge, 3 new/changed REST params), an
entirely new "All Valuations" dashboard page (`valuations.html`/`valuations.js`, 264 lines,
Chart.js from an unpinned CDN, sortable table, live-price polling), two new REST endpoints
(`/api/valuations`, `/api/live-prices`), a `FAIR VALUE` verdict band, and — the single highest-
severity item in this report — **the removal of the growth-rate ceiling** (`clampGrowthRate.ts`
now only floors at -5%; `GROWTH_RATE_CAP_PERCENT` no longer exists) while **three separate docs**
(CLAUDE.md and both `wiki/ארכיטקטורה.md` and `wiki/שיטות-הערכה.md`) still assert a hard `[-5%,
25%]` band with the literal old constant name. None of the new feature work is documented in
CLAUDE.md, README.md, or any wiki page. Worse, `CURRENT_WORK.md`'s own "Next up" section and the
dedicated `PLAN_2026-08-27_feature-tasks.md` still describe this work as **"not started"** and
specify an architecture (`src/evaluators/` module, `evaluators.json`, `EVALUATORS_FILE_PATH`,
`GET/POST/DELETE /api/evaluators`) that was never built — what actually shipped lives inside
`src/history/` instead, with a client-side-only, `localStorage`-backed evaluator list. The
project's own internal planning docs are now dead references to a design that doesn't exist.
The evaluator feature is also web-only — the CLI has no equivalent flag — which is exactly the
class of adapter-divergence CLAUDE.md's own "Gotchas" section warns against elsewhere. The
`valuations.js` dashboard and the entire evaluator-storage subsystem in `src/history/` also have
zero test coverage.

## Findings

> All `file:line` references below describe the state **at audit time**, before any fix. Line
> numbers in `CLAUDE.md`, `README.md`, `CURRENT_WORK.md`, and the wiki have since shifted —
> see "Resolution" at the end of this report for what changed.

### Documentation Accuracy

| Area | Doc Says | Code Does | Status |
|------|----------|-----------|--------|
| Growth-rate clamp | CLAUDE.md:137-138 — `shared/clampGrowthRate.ts` clamps every growth rate to `[-5%, 25%]`; wiki/ארכיטקטורה.md:90 — same `[-5%, 25%]`; wiki/שיטות-הערכה.md:13 — `GROWTH_RATE_CAP_PERCENT = 25` | The cap was deliberately removed per a 2026-08-27 user decision (`CURRENT_WORK.md:355-361`) — `clampGrowthRate.ts` (whole file, 6 lines) now only exports `GROWTH_RATE_FLOOR_PERCENT = -5` and does `Math.max(GROWTH_RATE_FLOOR_PERCENT, g)`; no ceiling constant exists anywhere in the codebase; `clampGrowthRate.test.ts:16-18` explicitly asserts "leaves a high value unchanged (no ceiling)" | **Mismatch** — same stale fact in 3 separate docs |
| Yahoo `ruleOf40` formula | CLAUDE.md:80-85 — `ruleOf40 = (revenueGrowth + ebitdaMargins) * 100`, both fields read straight off Yahoo's `financialData`, hand-verified NVDA example `0.852 + 0.65294 = 1.50494 → 150.494` | Growth numerator is no longer `financialData.revenueGrowth` (quarterly YoY) — it's `deriveAnnualRevenueGrowth` from a **separate** `fetchAnnualRevenueSeries` call (`src/data/yahoo/client.ts:63-70`, `src/data/yahoo/index.ts:34-50,113`), period-matched to `ebitdaMargins` (TTM). A new `ebitdaMarginIsTrustworthy` guard (`index.ts:107-109`) also nulls the result when `ebitdaMargins===0` is ambiguous (no-EBITDA vs. genuinely-breakeven vs. negative-EBITDA cases). The doc's own NVDA example is now contradicted by the equivalent test: same inputs now assert `130.768`, not `150.494` (`index.test.ts:215-234`); `CURRENT_WORK.md:59` records the live-verified NVDA change as `150.49 → 130.77` | **Mismatch** — doc describes the pre-fix formula and cites a now-wrong worked example |
| `src/history/` architecture | CLAUDE.md:118-135 — single `HISTORY_FILE_PATH`-backed `history.json`, no mention of evaluators | A parallel per-evaluator storage path exists: `resolveHistoryFilePath` (`store.ts:10-19`) resolves to `data/evaluators/<sanitized-name>.json` when an `evaluator` arg is passed; `getHistory` (`index.ts:65-134`) merges matching records from the legacy `history.json` when an evaluator is given, or merges every evaluator file plus legacy when none is given; `getAllLatestValuations` (`index.ts:194-231`) reads every file under `data/evaluators/` to compute one latest-per-ticker record. None of this is in CLAUDE.md | **Missing** |
| Web REST surface | CLAUDE.md:202-208 lists exactly the 14 current `/api/valuate` body fields (this part is now accurate — see Comparison below) plus `GET /api/history?ticker=`, `POST /api/history`, `DELETE /api/history/:id`, with no `evaluator` param mentioned anywhere | `GET /api/history` and `DELETE /api/history/:id` both also accept `?evaluator=` (`server.ts:246-248,306-309`); `POST /api/history`'s body also accepts `evaluator?: string` (`server.ts:297`); two entirely new endpoints exist, `GET /api/valuations` (`server.ts:255-261`) and `GET /api/live-prices?tickers=` (`server.ts:263-295`) | **Missing** |
| MoS dropdown | CLAUDE.md:155 — "the web UI's four-value MoS dropdown" (singular) | Confirmed singular again — one `<select id="mos-select">` (`index.html:74`), no `bear-mos-select`/`bull-mos-select` remain | **Match** (Resolved since 2026-08-22 — see Comparison) |
| `yahoo/types.ts` import exception | CLAUDE.md:72-77 — explicitly documents `types.ts` as an intentional shared-type exception | `cache.ts`/test files still import `AnalystConsensus` from `./yahoo/types` — matches the doc's revised wording exactly | **Match** (Resolved since 2026-08-22 — see Comparison) |
| CLI/web growth-fallback chain "byte-identical" | CLAUDE.md:164-175 | Still identical: `analystEstimate5y ?? historical3y ?? historical1y`, `src/cli/index.ts:132-134` vs. `src/web/server.ts:151-154` | Match |
| `income_statement` outputsize | CLAUDE.md:289-299 (Gotchas) — quarterly bumped 4→6 for `calculateTtmEpsGrowthPercent`, annual also 6, both are the plan-tier ceiling | Confirmed: both calls now request `outputsize=6` (`client.ts:113,125`) | Match |
| CLI `-m/--mos`, `-n/--notes` flags | README.md:53-57 documents both | Present, `src/cli/index.ts:180-181` | Match (Resolved since 2026-08-22 — see Comparison) |
| Evaluator feature — CLI parity | `CURRENT_WORK.md:349` states the evaluator feature "must work from both the web UI and the CLI so the two adapters don't diverge" | `src/cli/index.ts:179-182`'s full flag list has no evaluator equivalent — `-H/--history` cannot filter by evaluator, `--save` cannot attach one | **Mismatch** — shipped behavior violates the project's own stated requirement for this feature |
| "Latest valuation per (ticker, evaluator)" | `CURRENT_WORK.md:378` — "when more than one evaluator exists, the latest per (ticker, evaluator) pair" | `getAllLatestValuations` (`history/index.ts:216-222`) dedups by `record.ticker` alone — one evaluator's newer save silently hides another evaluator's valuation for the same ticker on the dashboard | **Mismatch** — worth confirming with the user whether this is an intentional simplification or a missed requirement, since it's a real behavior difference two evaluators would notice |

### Undocumented Code

- **Entire per-evaluator history subsystem** — `data/evaluators/<name>.json` storage
  (`src/history/store.ts:10-19`), legacy-file merge-by-evaluator (`src/history/index.ts:73-102`),
  `getAllLatestValuations` (`src/history/index.ts:194-231`), and the `evaluator` param on 3 REST
  endpoints (`server.ts:246-248,297,306-309`). Not in CLAUDE.md, README.md, or any wiki page.
- **`GET /api/valuations`** (`server.ts:255-261`) and **`GET /api/live-prices?tickers=`**
  (`server.ts:263-295`, calls `yahoo-finance2`'s `quote()` directly, independent of the cached
  `fetchAnalystConsensus` path) — two undocumented REST endpoints.
- **`src/web/public/valuations.html` + `valuations.js`** (264 lines) — a full second frontend
  page: sortable table (`valuations.html:46-55`, 8 sortable columns), an evaluator filter
  dropdown, a "🔄 Refresh Live Prices" flow hitting `/api/live-prices`, and a Chart.js bar chart
  of Rule #1 upside per ticker (`valuations.js:150-215`). Reachable via an "All Valuations" nav
  link in `index.html:23`. No mention in README's "Web UI" section or anywhere else.
- **Chart.js dependency** — loaded via `<script src="https://cdn.jsdelivr.net/npm/chart.js">`
  (`valuations.html:12`) with **no version pinned**, and not present in `package.json` at all
  (grep for "chart" in `package.json` returns nothing). Undocumented as a dependency, and the
  missing version pin means a future breaking Chart.js release could silently change the
  dashboard's behavior with no code change on this side to point to.
- **Client-side evaluator list** — `app.js:1070-1116`'s `renderEvaluators`/add/delete flow
  stores the managed name list in `localStorage.getItem('evaluatorsList')` (default
  `['Aviv', 'Ran']`), per-browser, not server-side. This is the opposite of what
  `CURRENT_WORK.md:339-343` specifies (a disk-backed store "usable from the CLI too and
  consistent across browsers/devices") — see Dead References below.
- **`FAIR_VALUE_TOLERANCE_PERCENT = 10`** (`app.js:46`, used in `renderVerdict`, `app.js:426`) —
  a new named threshold with no mention in CLAUDE.md's Constants or anywhere else.
- **Server bind-to-loopback + Tailscale Serve reliance** (`server.ts:322-323`, "Keep the app
  private; Tailscale Serve provides the authenticated HTTPS entry point") — a real security-
  relevant deployment decision from commit `0f1439b`, not mentioned in CLAUDE.md's Commands or
  Gotchas sections.

### Dead References

- **`PLAN_2026-08-27_feature-tasks.md` describes an architecture that was never built.** Lines
  214-374 (Hebrew, task 1 "שדה מבצע הערכת השווי") specify a dedicated `src/evaluators/` module
  (`index.ts`/`store.ts`/`types.ts` + tests, explicitly modeled on `src/history/`), a
  project-root `evaluators.json` overridable via an `EVALUATORS_FILE_PATH` env var, and
  `GET/POST/DELETE /api/evaluators` endpoints. None of `src/evaluators/`, `EVALUATORS_FILE_PATH`,
  or `/api/evaluators` exist anywhere in the current codebase (confirmed: no such directory, zero
  grep hits for the env var name, zero grep hits for the route in `server.ts`). The feature was
  built instead inside `src/history/` with a client-side `localStorage` name list. This plan
  document is now a reference to a design decision that was superseded during implementation but
  never updated to say so.
- **`CURRENT_WORK.md:328` — "Requested features (2026-08-27, from user) — not started"** header
  is itself a dead/stale claim: all 6 items under it (evaluator field, FAIR VALUE label, growth
  cap removal, bear/bull % diff display, valuations table, sorting/filtering) are implemented and
  shipped as of today's `HEAD` (`4576c8f`) — see the Documentation Accuracy rows above and the
  Comparison section below for per-item evidence. The session log that's supposed to be read
  "before doing anything else" (CLAUDE.md:265-266) currently tells a new session the opposite of
  reality for this entire feature set.
- **`TASKS.md`** is a fully-resolved punch-list from the 2026-08-16 audit (all 8 items `[x]`) —
  no longer an actionable doc, but not a dead *reference* since it doesn't claim anything false
  about current state; safe to archive or leave as historical record.

### Configuration Alignment

| Variable | .env.example | CLAUDE.md | Code Usage | Status |
|----------|--------------|-----------|------------|--------|
| `TWELVE_DATA_API_KEY` | Yes (uncommented, required) | Yes (Commands) | `src/data/twelvedata/env.ts:6` | Match |
| `PORT` | Yes (commented, optional) | Yes (Commands) | `src/web/server.ts:16` | Match |
| `CACHE_DIR_PATH` | Yes (commented, optional) | Yes (Gotchas) | `src/data/cache.ts` | Match |
| `HISTORY_FILE_PATH` | Yes (commented, optional) | Yes (Gotchas) | `src/history/store.ts` | Match |
| `EVALUATORS_FILE_PATH` | Not present | Not present | Not present anywhere in code (only in the superseded plan doc) | N/A — planned but never built; not a real gap |

`.gitignore` gained a blanket `data/` entry (commit `4576c8f`, "per-evaluator local state, like
history.json") alongside the pre-existing specific `history.json`/`history-*.json` lines — this
is a real, sensible config change but isn't mentioned in any doc either (minor, folded into the
evaluator-subsystem recommendation below rather than listed separately).

### Constants & Weights Verification

| Constant | Documented Value | Code Value | File:Line | Status |
|----------|-------------------|------------|-----------|--------|
| Growth-rate clamp floor | -5% | -5 | `src/valuation/shared/clampGrowthRate.ts:2` | Match |
| Growth-rate clamp cap | 25% (CLAUDE.md:138, wiki x2) | **No cap exists** | `src/valuation/shared/clampGrowthRate.ts` (whole file) | **Mismatch** (see Documentation Accuracy) |
| `mosPercent` valid range / default | `[0, 100)`, default 0 | Unchanged | `src/valuation/ruleOne/index.ts:24,48` | Match |
| Cache TTL | 24h | `24 * 60 * 60 * 1000` ms | `src/data/twelvedata/index.ts`, `src/data/yahoo/index.ts:57` | Match |
| Bear/Bull growth derivation | Documented (CLAUDE.md:187-189) `*0.75`/`*1.25`, `-3`/`+3` fallback | Confirmed exactly | `server.ts:174-179,193-198` | Match |
| Bear/Bull default Exit P/E, Req. return | Documented (CLAUDE.md:190-191) 10/15%, 20/12% | Confirmed | `server.ts:184-185,203-204` | Match |
| Quarterly/annual `outputsize` | 6 / 6 (CLAUDE.md Gotchas) | 6 / 6 | `client.ts:113,125` | Match |
| `FAIR_VALUE_TOLERANCE_PERCENT` | Undocumented | 10 | `app.js:46` | Missing from docs |
| Rule of 40 `ebitdaMarginIsTrustworthy` guard | Undocumented | 4-case guard (see Documentation Accuracy) | `src/data/yahoo/index.ts:107-109` | Missing from docs |

### Test Coverage

Measured by actually running the suite (`npx vitest run`), not estimated.

**Correction to an earlier draft of this report:** a first pass concluded the suite could not be
run here and fell back to a static `grep` count of 240. Both halves of that were wrong. Node
*is* installed (`/usr/bin/node`, v18.19.1 — the initial `which node` miss was a PATH artifact),
and the real blocker was only that vitest's bundler needs `styleText` from `node:util`, i.e.
**Node 20.12+**; under a Node 22 toolchain the suite runs fine. The static grep also undercounted
by 5 (it missed multi-line `it(` declarations, all in `server.test.ts`). The true baseline at the
start of this audit was **245 tests across 16 files, all passing**, with `tsc` clean.

`npm run lint` was **red at baseline**: 11 errors / 3 warnings. Six of the errors come from an
untracked local `.venv/` (a Python virtualenv that `eslint.config.js` doesn't ignore — not repo
code). The other 5 errors and all 3 warnings were real, all in `src/history/index.ts` — `any`
types, an empty `catch` block, and a `prefer-const` — introduced by the evaluator commits. Note
`eslint.config.js` ignores `src/web/public/**`, so neither `app.js` nor `valuations.js` is linted
at all.

| File | Tests (baseline) |
|------|-----------------|
| `src/web/public/app.test.js` | 77 |
| `src/web/server.test.ts` | 29 |
| `src/data/twelvedata/normalize.test.ts` | 25 |
| `src/data/yahoo/index.test.ts` | 23 |
| `src/data/twelvedata/index.test.ts` | 14 |
| `src/data/twelvedata/client.test.ts` | 13 |
| `src/valuation/ruleOne/index.test.ts` | 10 |
| `src/cli/index.test.ts` | 9 |
| `src/valuation/lynch/index.test.ts` | 9 |
| `src/history/index.test.ts` | 7 |
| `src/cli/formatOutput.test.ts` | 6 |
| `src/data/twelvedata/historicalPe.test.ts` | 6 |
| `src/data/cache.test.ts` | 5 |
| `src/data/resolveEps.test.ts` | 5 |
| `src/valuation/shared/clampGrowthRate.test.ts` | 4 |
| `src/data/yahoo/client.test.ts` | 3 |
| **Total** | **245** |

Coverage gaps:

| Module/Feature | Has Tests | Notes |
|----------------|-----------|-------|
| `src/web/public/valuations.js` (264 lines: table render, sort, evaluator filter, live-price refresh, Chart.js rendering) | **No** | No test file exists at all — the largest untested surface in the project |
| `src/history/` evaluator storage (`resolveHistoryFilePath`'s evaluator branch, legacy-merge logic in `getHistory`, `getAllLatestValuations`) | **No** | `history/index.test.ts`'s 7 tests never pass an `evaluator` argument or reference `data/evaluators`; the only test touching "evaluator" anywhere is `app.test.js` asserting a fetch URL string (`?evaluator=Aviv`), not the backend behavior |
| `renderHistoryTable` legacy-vs-scenario branching | Yes | **Resolved since 2026-08-22** — `app.test.js:1160-1252` |
| `src/history/` base/bear/bull round-trip | Yes | **Resolved since 2026-08-22** — `history/index.test.ts:195-260` |
| `src/data/twelvedata/env.ts` | **No** | Still only ever mocked out (`index.test.ts:14`) — unchanged from 2026-08-22, still unfixed |
| `src/history/store.ts`'s `HISTORY_FILE_PATH`-env-var/default-path branch | **No** | `index.test.ts` still always passes an explicit path override — unchanged from 2026-08-22, still unfixed |
| `src/data/yahoo/client.ts` `fetchAnnualRevenueSeries` | Yes | New, added alongside the period-mismatch fix — `client.test.ts:41-70` |
| Rule of 40 `ebitdaMarginIsTrustworthy` guard | Yes | Well covered — `index.test.ts:237-393` (falsy-zero, period-mismatch, and all-null-input cases) |

## Comparison with Previous Reports

### Since 2026-08-22 Report

| Prior Finding | Status | Evidence |
|----------------|--------|----------|
| 3-scenario feature entirely missing from CLAUDE.md | **Resolved** | CLAUDE.md:177-208 now documents the nested response, all 14 body fields, growth-derivation formula, defaults |
| `SavedValuation` legacy/scenario dual shape missing from CLAUDE.md | **Resolved** | CLAUDE.md:127-135 |
| Outputsize sentence conflated quarterly/annual | **Resolved (differently than recommended)** | The prior recommendation was to fix the *doc* to say quarterly=4; instead the *code* changed — quarterly was bumped to 6 (2026-08-26, for `calculateTtmEpsGrowthPercent`) and CLAUDE.md now correctly describes both as 6. Net effect is the same (doc and code agree) but via the opposite mechanism than recommended |
| README missing `-m/--mos`, `-n/--notes` | **Resolved** | README.md:53-57 |
| `renderHistoryTable` legacy-vs-scenario branching untested | **Resolved** | `app.test.js:1160-1252` |
| `src/history/` base/bear/bull round-trip untested | **Resolved** | `history/index.test.ts:195-260` |
| `yahoo/types.ts` import-exception wording overreach | **Resolved** | CLAUDE.md:72-77 now states the exception explicitly |
| Web redesign documented only in `wiki/Home.md`, not README/CLAUDE.md | **Still Unfixed** | Still true today — neither doc mentions the editorial redesign; now compounded by the valuations dashboard being undocumented everywhere, not just missing from the two primary docs |
| `env.ts` untested | **Still Unfixed** | `index.test.ts:14` still only mocks it |
| `store.ts` `HISTORY_FILE_PATH` branch untested | **Still Unfixed** | Same gap, unchanged |

No prior finding was Stale (none of the 2026-08-22 report's specific claims have since become
wrong in the other direction — i.e., nothing it called a genuine match has since silently broken
without a corresponding new finding above already covering it).

## Recommendations

1. **Fix the growth-rate-cap claim in all three docs that state it** — CLAUDE.md:137-138,
   `wiki/ארכיטקטורה.md:90`, and `wiki/שיטות-הערכה.md:13,114`. Replace "`[-5%, 25%]`" /
   "`GROWTH_RATE_CAP_PERCENT = 25`" with a statement that only a `-5%` floor remains
   (`GROWTH_RATE_FLOOR_PERCENT`, `src/valuation/shared/clampGrowthRate.ts`), and note the
   2026-08-27 decision to drop the ceiling deliberately (context already recorded in
   `CURRENT_WORK.md:355-361`, just needs porting into the docs that actively describe current
   behavior). Highest priority: this is a core valuation rule stated with a specific wrong number
   in the file loaded every session, and it's wrong in three places at once.
2. **Update CLAUDE.md's `ruleOf40` paragraph (lines 78-89)** to describe the current
   period-matched formula: growth now comes from `deriveAnnualRevenueGrowth`
   (`src/data/yahoo/index.ts:34-50`, backed by `fetchAnnualRevenueSeries`,
   `src/data/yahoo/client.ts:63-70`), not `financialData.revenueGrowth` directly, and mention the
   `ebitdaMarginIsTrustworthy` guard (`index.ts:107-109`). Either update the NVDA worked example
   to the new `130.768` figure (`CURRENT_WORK.md:59` already has it) or remove the specific
   numbers and just describe the mechanism.
3. **Add an evaluator subsystem section to CLAUDE.md's `src/history/` writeup** (currently
   lines 118-135) describing: `data/evaluators/<name>.json` storage
   (`store.ts:10-19`), the legacy-file merge behavior in `getHistory` (`index.ts:73-102`),
   `getAllLatestValuations` (`index.ts:194-231`), and the `evaluator` param on the three REST
   endpoints that accept it. Also extend the "Web REST surface" section (lines 202-208) with the
   two missing endpoints, `GET /api/valuations` and `GET /api/live-prices?tickers=`
   (`server.ts:255-295`).
4. **Document the "All Valuations" dashboard page** in both CLAUDE.md's Architecture and
   README's "Web UI" section — it's reachable from the app's own nav (`index.html:23`) and is a
   real, user-facing surface (`src/web/public/valuations.html`/`valuations.js`). Include the
   Chart.js CDN dependency (`valuations.html:12`) as an undocumented dependency, and separately
   flag that it's unpinned (`chart.js` with no version) as worth pinning regardless of the doc
   fix, since a future Chart.js release could change behavior silently.
5. **Correct `CURRENT_WORK.md`'s "Next up" section (line 328) and either delete or clearly
   mark `PLAN_2026-08-27_feature-tasks.md` as superseded.** All 6 "not started" items are
   actually shipped; the plan file's `src/evaluators/`/`EVALUATORS_FILE_PATH`/`/api/evaluators`
   design was abandoned in favor of the `src/history/`-integrated approach that shipped instead.
   This is the highest-value fix among the "internal docs" group, since `CURRENT_WORK.md` is the
   file CLAUDE.md instructs every session to read first (CLAUDE.md:265-266) — right now it
   actively misleads a fresh session about what exists.
6. **Decide and document the evaluator/CLI parity gap.** The evaluator feature is currently
   web-only (`src/cli/index.ts:179-182` has no equivalent flag), which contradicts
   `CURRENT_WORK.md:349`'s own stated requirement that it "work from both the web UI and the CLI
   so the two adapters don't diverge." Either add CLI support (a `--by <name>`/`--evaluator`
   flag, mirroring `-n/--notes`) or explicitly document the CLI as evaluator-unaware and why —
   the same choice this project already made once for the Yahoo-analyst-data CLI/web gap
   (`TASKS.md`'s resolved task 6).
7. **Confirm the "latest per (ticker, evaluator)" behavior with the user.**
   `getAllLatestValuations` (`history/index.ts:216-222`) currently dedups by ticker alone, so if
   two evaluators both value the same ticker, only the more recent one shows on the dashboard —
   different from what `CURRENT_WORK.md:378` specified. This may be an intentional
   simplification, but it's a real behavior difference worth a deliberate decision rather than a
   silent one, and whichever way it's decided, it should be written down (task 5's outcome, not
   its original spec).
8. **Add test coverage for `src/web/public/valuations.js`** — it's the single largest untested
   file added since the last report (264 lines: table render/sort, evaluator filter, live-price
   fetch, chart rendering) and has zero test infrastructure. At minimum, mirror `app.test.js`'s
   pattern (load the script via `new Function`, export the pure render/sort helpers) and cover
   the sort comparator and the legacy-vs-scenario record handling this page also has to deal
   with.
9. **Add a `src/history/` test for the evaluator storage path** — a save/read round-trip
   through `data/evaluators/<name>.json` (mirroring the existing base/bear/bull round-trip test
   at `history/index.test.ts:195`), plus one case for the legacy-`history.json`-merge behavior in
   `getHistory` (`index.ts:73-102`), since that merge logic currently has no test at all despite
   being the mechanism that makes old pre-evaluator records still show up.
10. **Optional/low-priority carryovers from 2026-08-22, still unfixed**: `src/data/twelvedata/
    env.ts`'s real validation logic is still only ever mocked out in tests (`index.test.ts:14`);
    `src/history/store.ts`'s `HISTORY_FILE_PATH`-env-var and default-path branches are still
    never hit because `history/index.test.ts` always passes an explicit path override.


---

## Resolution — all recommendations addressed (2026-08-28)

Every recommendation above was implemented the same day this report was written. Final state:
**289 tests across 18 files, all passing** (baseline 245/16); `tsc` build clean; `eslint src/`
clean (the 5 real lint errors and 3 warnings in `src/history/index.ts` were fixed as part of
editing that file; the 6 remaining errors in the untracked `.venv/` are not repo code).

Two items required user decisions, both taken before implementation:
- **Rec 6 (CLI evaluator parity)** — decided: keep the CLI deliberately evaluator-unaware and
  document why, rather than adding a flag. Same resolution the project already chose for the
  Yahoo-analyst CLI/web gap.
- **Rec 7 (dashboard dedup)** — decided: fix it. `(ticker, evaluator)` is now the key.

| # | Recommendation | Resolution |
|---|----------------|-----------|
| 1 | Growth-rate cap stale in 3 docs | Fixed in `CLAUDE.md`, `wiki/ארכיטקטורה.md`, `wiki/שיטות-הערכה.md` (incl. the historical-incident line that referenced the old band). Each says floor-only, names the 2026-08-27 decision, and notes the asymmetric effect on Rule #1. |
| 2 | `ruleOf40` paragraph describes pre-fix formula | Rewritten: annual period-matched numerator via `deriveAnnualRevenueGrowth`/`fetchAnnualRevenueSeries`, the no-quarterly-fallback rule, the `ebitdaMarginIsTrustworthy` guard, and the corrected NVDA figure (`130.768`, was `150.494`). |
| 3 | Evaluator subsystem + 2 REST endpoints undocumented | New "Per-evaluator storage" block in CLAUDE.md's `src/history/` section; REST surface expanded to all 6 endpoints with their `evaluator` params. Includes the `HISTORY_FILE_PATH`-beats-evaluator precedence wart. |
| 4 | Dashboard + Chart.js undocumented; version unpinned | Documented in CLAUDE.md and README (new "All Valuations page" section). **Code fix:** Chart.js pinned to `4.4.7` with an SRI `integrity` hash, replacing the floating `npm/chart.js` URL. |
| 5 | `CURRENT_WORK.md` "not started"; `PLAN_*.md` specifies unbuilt design | Both corrected. Each of the 6 features now carries a ✅ SHIPPED status with any spec-vs-reality divergence called out; the plan file opens with a SUPERSEDED banner naming exactly what was never built (`src/evaluators/`, `evaluators.json`, `EVALUATORS_FILE_PATH`, `/api/evaluators`). |
| 6 | CLI evaluator parity gap | Documented as a deliberate choice in CLAUDE.md's "CLI flags" section, including what a future implementation must reuse. README notes CLI saves show as unowned. |
| 7 | Dashboard dedups by ticker alone | **Code fix:** `getAllLatestValuations` now keys on `(ticker, evaluator)`. Regression test written first and confirmed failing on the old key (`expected [ 'b-1' ] to deeply equal [ 'a-1', 'b-1' ]`). Chart labels now qualify a repeated ticker with the evaluator name, since one ticker can now legitimately appear twice. |
| 8 | `valuations.js` has zero coverage | New `src/web/public/valuations.test.js`, **28 tests**, using the same `new Function` harness as `app.test.js`. Covers `fmt`, `parsePct`, both record shapes, the zero-price guard, filtering, all sort columns, the evaluator filter, and the chart. |
| 9 | No test for evaluator storage path | **13 tests added** to `src/history/index.test.ts`: evaluator-file routing and name sanitization, per-evaluator isolation, both legacy-merge branches, and the `(ticker, evaluator)` dedup. They exercise the real on-disk paths (an injected `filePath` short-circuits the very branches under test) under vitest-only names, and back up/restore `history.json` so a real user's data is never replaced. |
| — | *(not in the original recommendations)* | **Code fix:** `.gitignore`'s bare `data/` also matched `src/data/`, hiding new files there from git — anchored to `/data/`. See "Three real bugs" below. |
| 10 | Carryovers: `env.ts`, `store.ts` path branches | Both closed. New `src/data/twelvedata/env.test.ts` (3 tests, incl. empty-string-is-missing); `resolveHistoryFilePath` now has 6 tests covering explicit path, env var, evaluator, blank evaluator, default, and the env-var-beats-evaluator precedence. |

### Three real bugs found while implementing

None were in the report above — all three surfaced from doing the work it asked for:

1. **The dashboard's Ticker and Evaluator columns never sorted at all.** The sort comparator's
   missing-value guard was `isNaN(valA)`, and `isNaN('AAPL')` is `true`, so both sides were
   classed as missing, the comparator returned `0` for every string pair, and the `localeCompare`
   branch below it was unreachable. Both columns advertise themselves as sortable (`⇕` in the
   header). Fixed by only falling back to `isNaN` for values that aren't usable strings.
2. **`getAllLatestValuations` hid a second evaluator's row** — the rec-7 item above, confirmed by
   a failing-first test rather than by inspection alone.
3. **`.gitignore`'s `data/` pattern also ignored `src/data/`.** A bare `data/` in gitignore
   matches a directory of that name at *any* depth, so commit `4576c8f` ("Ignore data/") silently
   made every **new** file under `src/data/` invisible to git. Existing files there stayed visible
   only because they were already tracked, which is exactly why nobody noticed. It surfaced here
   because the new `src/data/twelvedata/env.test.ts` did not appear in `git status` — it would
   have been dropped from the commit without a word. Fixed by anchoring the pattern to `/data/`;
   verified that the project-root `data/evaluators/` is still ignored and `src/data/` is not.
   This one is worth remembering: it is silent, it only affects future files, and it was one
   `git add` away from losing work.

### Verification

```
npm test          → 289 passed (18 files)
npm run build     → clean (tsc)
npx eslint src/   → clean
```

Tests require **Node 20.12+** (vitest's bundler needs `node:util`'s `styleText`); the app itself
still runs on Node 18. `node_modules` must be installed under the same Node major that runs the
tests, or rolldown's native binding won't match. This is now recorded in `CURRENT_WORK.md` and
`README.md`, since the system Node on the workstation is 18.19.1 and the failure mode is a
misleading `SyntaxError`.
