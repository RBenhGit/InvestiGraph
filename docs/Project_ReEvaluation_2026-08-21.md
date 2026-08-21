# Project Re-Evaluation Report
**Date:** 2026-08-21
**Focus:** Full Project — Documentation vs Implementation alignment
**Method:** Two parallel specialist agents (architecture/data-flow scanner + config/constants/test-coverage scanner) plus direct independent verification of every finding before inclusion.

## Executive Summary

The baseline is green: **113/113 tests pass**, `eslint` clean, `tsc` clean (verified live via the documented SSH host, not the broken `Z:` mount). No bugs found in running code. However, **`CLAUDE.md` (and `wiki/`) have drifted significantly** since the last re-evaluation (`docs/Project_ReEvaluation_2026-08-16.md`): three entire features shipped on 2026-08-19 — a disk-backed **offline cache** (`src/data/cache.ts`), a **valuation history/persistence module** (`src/history/`), and a **Margin-of-Safety parameter** on `calculateRuleOneValue` — are completely unmentioned in `CLAUDE.md`. Most importantly, the cache addition makes CLAUDE.md's repeated claim *"neither has a mocked/offline mode"* **factually false**: both `fetchStockData` and `fetchAnalystConsensus` now serve stale cached data on API failure. A secondary but real thread: the newest UI logic (Scenarios/MoS/Notes/History) and the CLI's newest flags exist and work (per manual behavior and integration tests one layer down) but are **not directly unit-tested** at their own layer.

## Findings

### Documentation Accuracy

| Area | Doc Says | Code Does | Status |
|------|----------|-----------|--------|
| Offline/mocked mode | CLAUDE.md:20-21, 174-175 — "neither has a mocked/offline mode"; requires live API key "to do anything" | `src/data/twelvedata/index.ts:205-210` and `src/data/yahoo/index.ts:79-85` fall back to a stale disk cache on fetch failure and return `{ ok: true }` | **Mismatch (factual)** |
| `src/data/cache.ts` module | Not mentioned anywhere | Read-through cache (24h TTL) + stale-on-error fallback, shared by both `twelvedata/` and `yahoo/`; sits directly under `src/data/` as a sibling, not inside either module | **Missing** |
| `src/history/` module | Not mentioned anywhere | Full CRUD-style module (`saveValuation`/`getHistory`/`deleteValuation`), `{ ok }` discriminated-union convention consistent with the rest of the codebase, `index.ts`-only-entry-point pattern (unstated but followed in practice) | **Missing** |
| `calculateRuleOneValue` signature | CLAUDE.md:33 — `(eps, growth, exitPe, requiredReturn, years)`, 5 params | `src/valuation/ruleOne/index.ts:18-25` — 6 params, `mosPercent: number = 0` added, plus a new `INVALID_MOS` validation branch and `mosPrice` in `intermediate` | **Mismatch** |
| `fetchStockData`/`fetchAnalystConsensus` signatures | CLAUDE.md:30-31 — `fetchStockData(ticker) -> StockDataResult`, single-arg | Both now accept an optional second `{ forceRefresh?, maxAgeMs? }` options object | **Mismatch** |
| `POST /api/valuate` body | CLAUDE.md:35 — undocumented body shape | `epsOverride`, `mosPercent`, `forceRefresh` all added to `ValuateRequestBody` | **Missing (partial)** |
| Web REST surface | CLAUDE.md:35 — only `POST /api/valuate` documented | `GET /api/history`, `POST /api/history`, `DELETE /api/history/:id` all exist and are tested | **Missing** |
| CLI flags | CLAUDE.md:34 — "thin wrapper... formats to stdout", no flags mentioned | `-s/--save`, `-m/--mos <percent>`, `-n/--notes <text>`, `-H/--history [ticker]` all implemented (test coverage caveat below) | **Missing** |
| Growth clamp range `[-5%, 25%]` | CLAUDE.md:68-69 | `clampGrowthRate.ts:2-3` — `GROWTH_RATE_FLOOR_PERCENT = -5`, `GROWTH_RATE_CAP_PERCENT = 25` | ✅ Match |
| `historicalPe` median/annual description | CLAUDE.md:50-52 — median, annual EPS, `ceil(N/2)` | Matches `historicalPe.ts` exactly (fixed in the 2026-08-16 pass) | ✅ Match |
| CLI/web Yahoo divergence | CLAUDE.md:26-27 — CLI does not use `yahoo` | Still true — grep confirms zero `yahoo` references in `src/cli/index.ts` | ✅ Match |
| `TWELVE_DATA_API_KEY` single-read-point rule | CLAUDE.md:53-54 | Verified — `env.ts:6` is the only direct read in `src/` | ✅ Match |

### Undocumented Code

- **`src/data/cache.ts`** — `resolveCacheDir`, `saveCachedStockData`/`getCachedStockData`, `saveCachedYahooData`/`getCachedYahooData`. All cache-file I/O failures are silently swallowed (`catch {}`) by design ("caching failure should not fail the user's operation") — reasonable, but an undocumented design decision.
- **`src/history/`** (`types.ts`, `store.ts`, `index.ts`) — `store.ts` is internal-only (never imported outside the directory, consistent with but not stated as the module's convention); `index.ts` is the de facto single entry point, re-exporting types plus `saveValuation`/`getHistory`/`deleteValuation`/`formatHistoryError`.
- **Web UI**: Margin-of-Safety selector (`#mos-select`, values 0/10/25/50%), Bull/Base/Bear scenario buttons (`.scenario-btn[data-scenario]`), "Save this valuation" + Notes field, "Saved Valuations" table with filter/load/delete, "🔄 Refresh Live" button — none reflected in CLAUDE.md's architecture description of `src/web/`.
- **`resolveTtmEps`'s `apiEps` dead branch** — still accurate as documented in task 5 of the prior TASKS.md; `index.ts` always passes `null` for `apiEps` by design, so the API-preferred branch never runs in production. No new drift here, confirmed still correct.
- **MoS enforcement is two-layered and undocumented as such**: `calculateRuleOneValue`'s own validation (`ruleOne/index.ts:48`) accepts *any* value in `[0, 100)`, not just the four presets — the `{0, 10, 25, 50}` restriction is a **web-UI-only** convention (`index.html:76-80`'s fixed `<select>`), not enforced by the pure function or by the CLI's free-text `-m/--mos <percent>` flag. CURRENT_WORK.md's "0%, 10%, 25%, 50%" claim is accurate only for the web UI dropdown and doesn't scope itself that way.

### Dead References

None found. Every file path CLAUDE.md cites (`client.ts`, `env.ts`, `historicalPe.ts`, `normalize.ts`, `shared/clampGrowthRate.ts`, `src/cli/index.ts`, `src/web/server.ts`, `types.ts`) exists at the described location.

### Configuration Alignment

| Variable | `.env.example` | Read in code | Status |
|----------|---------------|---------------|--------|
| `TWELVE_DATA_API_KEY` | ✅ present (required) | `src/data/twelvedata/env.ts:6` — sole read point, as documented | ✅ Match |
| `PORT` | ✅ present (commented, documents default 3210) | `src/web/server.ts:19` | ✅ Match |
| `CACHE_DIR_PATH` | ❌ absent | `src/data/cache.ts:13` — optional override, defaults to `<project root>/cache` | **Missing from template** |
| `HISTORY_FILE_PATH` | ❌ absent | `src/history/store.ts:12` — optional override, defaults to `<project root>/history.json` | **Missing from template** |

Both missing vars are optional with safe defaults (same category as `PORT`, which *is* documented commented-out) — low severity, but the pattern set by `PORT` implies these should be too.

### Constants & Weights Verification

| Constant | Documented Value | Code Value | File:Line | Status |
|----------|-----------------|------------|-----------|--------|
| Growth-rate floor | -5% | -5 | `clampGrowthRate.ts:2` | ✅ Match |
| Growth-rate cap | 25% | 25 | `clampGrowthRate.ts:3` | ✅ Match |
| MoS allowed values (web UI) | Not documented in CLAUDE.md; CURRENT_WORK.md claims 0/10/25/50% globally | `index.html:76-80` — options `0`, `10`, `25` (selected), `50` — matches, but scoped to the web UI only | Web UI: ✅ Match. Global framing: **overstated** |
| MoS validation range (library) | Not documented | `ruleOne/index.ts:48` — rejects `NaN`, `< 0`, or `>= 100`; accepts any value in `[0, 100)` | **Missing** |
| Cache TTL | Not documented | `DEFAULT_CACHE_TTL_MS = 24h` in both `twelvedata/index.ts` and `yahoo/index.ts` | **Missing** |

### Test Coverage Gaps

| Module/Feature | Has Tests | Notes |
|----------------|-----------|-------|
| `src/data/cache.ts` | Thin | `cache.test.ts` — 72 lines, only 2 `it()` blocks for an 81-line module with TTL/`forceRefresh`/`CACHE_DIR_PATH` logic |
| `src/history/store.ts` | ❌ **No** | No dedicated test file, and no test imports from `./store` directly — its file I/O and the `HISTORY_FILE_PATH` env fallback are untested |
| `src/history/index.ts` — `saveValuation`/`getHistory`/`deleteValuation` | ❌ **No** | `index.test.ts` (193 lines, 5 tests) covers only the pure formatter helpers (`formatStockDataError`, `formatHistoryOutput`) — the module's actual CRUD logic is untested at this layer (though exercised indirectly via `server.test.ts`'s `/api/history` tests) |
| `src/valuation/ruleOne/index.ts` (mosPercent) | ✅ Yes | 10 tests, explicitly covers the MoS discount formula and the `INVALID_MOS` boundary (`>= 100`, negative) |
| `src/web/server.ts` (`/api/history` endpoints) | ✅ Yes | 11 tests, dedicated `describe` blocks for GET/POST/DELETE including a 404 case |
| `src/cli/index.ts` (`--save`/`-m`/`-n`/`-H`) | ❌ **No** | `commander` is fully mocked in `index.test.ts` (`option()` stubbed as a no-op returning `this`) — the real `.action()` callback with parsed flag values is never invoked. Only the pure `formatStockDataError`/`formatHistoryOutput` functions are tested; the flags exist and are wired in the real code but are unexercised by any test |
| `src/web/public/app.js` — Scenario/MoS/History/Notes UI | ❌ **No** | `app.test.js` has DOM fixtures for `#mos-select`, `.scenario-btn`, `#history-tbody`, `#history-filter` etc., but all 5 actual tests cover only `formatStockDataError` — none assert Scenario switching, MoS recompute, or history table behavior |

### Test Count Discrepancy

CURRENT_WORK.md (dated 2026-08-21 — today) states "110/110 tests passing" as of the 2026-08-19 log entry. The suite as it exists right now runs **113/113** (verified live via SSH: `15 test files, 113 tests, all passed`). This is most likely the log simply not being updated for 3 tests added since that entry (e.g. within `cache.test.ts`'s 2 tests + 1 elsewhere) rather than a real inconsistency — flagging per the skill's "flag ambiguous as Needs Review" instruction rather than assuming which is correct.

### Recommendations

Priority order, following the same low-risk-first structure as the prior `TASKS.md`:

1. **(High, docs-only)** Update CLAUDE.md's "no mocked/offline mode" claims (lines 20-21, 174-175) — this is now actively misleading, not just incomplete. State that a 24h-TTL disk cache exists and both data sources degrade to stale cached data (not failure) when the live API is unreachable.
2. **(High, docs-only)** Add `src/data/cache.ts` and `src/history/` to CLAUDE.md's Architecture tree and prose, following the same treatment given to `twelvedata/`/`yahoo/`.
3. **(Medium, docs-only)** Update `calculateRuleOneValue`'s documented signature to include `mosPercent`, note that its own validation accepts `[0,100)` (the 0/10/25/50 restriction is web-UI-only), and document the new REST endpoints (`GET/POST /api/history`, `DELETE /api/history/:id`) and CLI flags (`-s`, `-m`, `-n`, `-H`).
4. **(Low, config)** Add `CACHE_DIR_PATH` and `HISTORY_FILE_PATH` to `.env.example` as commented optional overrides, matching the existing `PORT` treatment.
5. **(Low, docs-only)** Sync `wiki/` pages — none currently mention cache, history, or MoS either; same content gap as CLAUDE.md.
6. **(Low, needs review)** Reconcile CURRENT_WORK.md's "110/110" with the live "113/113" — update the log line or confirm nothing regressed silently.
7. **(Low, optional feature work, not a doc fix)** Consider direct unit tests for `src/history/store.ts`, `src/history/index.ts`'s CRUD functions, the CLI's real `.action()` callback with the new flags, and the Scenario/MoS/History/Notes UI logic in `app.js` — these are covered indirectly (end-to-end via server/CLI integration or manual verification) but not at their own layer.

**Important:** As before, none of these findings are bugs in running code. The application works correctly; the cache and history features are exercised end-to-end and behave as intended. All findings are documentation lag from three features shipped in one session (2026-08-19) that were never folded back into CLAUDE.md/wiki, plus a few narrowly-scoped unit-test gaps one layer below already-passing integration coverage.
