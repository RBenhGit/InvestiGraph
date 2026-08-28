# Project Re-Evaluation Report
**Date:** 2026-08-22
**Focus:** Full Project

## Executive Summary

The core valuation logic (`src/valuation/`), the data-source modules (`src/data/twelvedata/`,
`src/data/yahoo/`, `src/data/cache.ts`), and the CLI/web fallback-chain parity claims in
CLAUDE.md all check out precisely against current code — no drift found there, and the recent
bear/bull hardcoding bug is confirmed genuinely fixed. The real finding this round is a
**documentation-sync gap, not a code bug**: two same-day feature commits
(`1a5dcc8`, `24a413b`, 2026-08-22) added a substantial 3-scenario (Bear/Base/Bull) feature —
6 new request fields, a nested `{base,bear,bull}` API response shape, 3 MoS dropdowns instead
of 1, and a new `SavedValuation` schema with legacy/scenario field splits — and none of it made
it into CLAUDE.md, which still describes the pre-scenario, single-MoS, flat-response world.
`CURRENT_WORK.md` (updated the same day) does document the feature accurately, so the two docs
are now out of sync with each other, not just with the code. Two smaller items also surfaced:
README.md is missing two real, working CLI flags (`-m/--mos`, `-n/--notes`), and the newest
UI code (`renderHistoryTable`'s legacy-vs-3-scenario branching, and the entire history
persistence path for `base`/`bear`/`bull`) has zero test coverage — the least-tested code is
also the newest and most recently buggy.

## Findings

### Documentation Accuracy

| Area | Doc Says | Code Does | Status |
|------|----------|-----------|--------|
| Module layout (`src/data/`, `src/valuation/`, `src/history/`, `src/cli/`, `src/web/`) | Described responsibilities per directory | Matches exactly | Match |
| `twelvedata/` sole entry point | Nothing outside imports `client.ts`/`normalize.ts`/`historicalPe.ts`/`env.ts` directly | Confirmed — zero external imports of those four files | Match |
| `yahoo/` sole entry point | "nothing outside this directory may import its `client.ts` **or `types.ts`**" | `client.ts` is never imported externally, but `types.ts` **is** — `src/data/cache.ts:5`, `src/data/cache.test.ts:12`, `src/web/server.test.ts:9` all `import type { AnalystConsensus } from './yahoo/types'` / `'../data/yahoo/types'` | Mismatch (doc overreach — `types.ts` is a reasonable, intentional exception for shared type shapes, but the literal wording forbids it) |
| `{ok:boolean}` error convention, no `throw` across module boundaries | Both layers use it end-to-end | Confirmed — internal `throw`s exist but are all caught and converted at each module's orchestration entry point before crossing out | Match |
| CLI/server growth-fallback chain "byte-identical" | `analystEstimate5y ?? historical3y ?? historical1y`, no cap, no default-to-0 | Confirmed byte-identical today: `src/cli/index.ts:96-100` vs. `src/web/server.ts:91-95` | Match |
| `calculateRuleOneValue`'s `mosPercent` | Optional, default 0, `[0,100)` else `INVALID_MOS`, `fairValue = stickerPrice*(1-mosPercent/100)` | Confirmed exactly — `src/valuation/ruleOne/index.ts:24,48,58` | Match |
| Growth-rate clamp | `[-5%, 25%]` in `shared/clampGrowthRate.ts`, called by both methods | Confirmed — `GROWTH_RATE_FLOOR_PERCENT=-5`, `GROWTH_RATE_CAP_PERCENT=25`, `shared/clampGrowthRate.ts:2-3`, called at `lynch/index.ts:30` and `ruleOne/index.ts:52` | Match |
| `ValuationResult` discriminated union | `epsTtm`/`growthRatePercent` accept `number\|null\|undefined`; returns `{ok:true,fairValue,inputs,intermediate?}\|{ok:false,error}` | Confirmed exactly, both functions | Match |
| `growth_estimates` 403 degrade | `.catch(() => null)` on non-Enterprise keys | Confirmed — `src/data/twelvedata/index.ts:111` | Match |
| `income_statement` quarterly `outputsize` cap | CLAUDE.md:222 — "rejects `period=quarterly&outputsize` above 6" | The **quarterly** call actually requests `outputsize=4` (`client.ts:111`); "6" is the **annual** call's value (`client.ts:123`) and separately the plan-tier's hard ceiling per the code's own comment. The sentence conflates two different numbers under one endpoint name. | Mismatch (imprecise, not a functional bug — the code itself explains the distinction in its own comment) |
| Yahoo `beta`/`priceToSales` raw pass-through, `ruleOf40` formula | Direct field reads, `ruleOf40=(revenueGrowth+ebitdaMargins)*100` | Confirmed exactly — `src/data/yahoo/index.ts:64-69,81-82` | Match |
| `cache.ts` 24h TTL / `CACHE_DIR_PATH` / `forceRefresh` | 24h TTL, dir override, bypass option | Confirmed, with one precision note: the 24h TTL constant lives in the two **consumer** modules (`twelvedata/index.ts:74`, `yahoo/index.ts:31`), not inside `cache.ts` itself (which is pure I/O, no TTL logic) — doc attributes it to `cache.ts` generally | Match (minor location imprecision) |
| `HISTORY_FILE_PATH` in `store.ts` | Overridable, defaults to `history.json` under project root | Confirmed — `src/history/store.ts:8,12` | Match |
| All 4 env vars (`TWELVE_DATA_API_KEY`, `PORT`, `CACHE_DIR_PATH`, `HISTORY_FILE_PATH`) | Documented in `.env.example` + CLAUDE.md Gotchas | Confirmed — every var used in code is documented in both places; no orphans either direction | Match |
| **Web UI's MoS dropdown** | CLAUDE.md:114 — "the web UI's **four-value dropdown**" (singular) | There are now **three** MoS `<select>` elements (`mos-select` base, `bear-mos-select`, `bull-mos-select`), each still 4 values (0/10/25/50%) — `src/web/public/index.html` | **Mismatch** — stale, pre-dates the 3-scenario feature |
| **`POST /api/valuate` body fields** | CLAUDE.md:139-140 — "body now also accepts `epsOverride`, `mosPercent`, `forceRefresh`" (3 fields mentioned total) | Actual `ValuateRequestBody` has **14** fields, including 6 entirely undocumented ones: `bearExitPeMultiple`, `bearRequiredReturnPercent`, `bearMosPercent`, `bullExitPeMultiple`, `bullRequiredReturnPercent`, `bullMosPercent` (`src/web/server.ts:21-39`) | **Mismatch** |
| **3-scenario Bear/Base/Bull feature** | Not mentioned anywhere in CLAUDE.md (verified via full-document grep for "bear"/"bull"/"scenario" — zero hits outside the stale MoS-dropdown line) | Substantial shipped feature: `server.ts:98-159` computes 3 independently-parameterized scenarios per method; response shape changed from flat `ValuationResult` to nested `{base,bear,bull}`; frontend (`app.js`) fully wired; `CURRENT_WORK.md` documents it in detail same-day | **Missing** from CLAUDE.md's Architecture section entirely |
| **`SavedValuation` shape** | CLAUDE.md:96-103 describes a flat record with "an optional MoS % and free-text notes/thesis" | Actual type now splits into legacy-optional flat fields **plus** new optional `base?/bear?/bull?: ScenarioValuation` (`src/history/types.ts:1-34`); `cli/index.ts:50` explicitly reads `r.base ?? r` to handle both shapes | **Missing** — doc describes only the pre-scenario shape |
| README.md CLI flags | Documents `--save`, `--history [ticker]` | Code also has `-m/--mos <percent>` and `-n/--notes <text>`, both real and working (`src/cli/index.ts:143-144`) — absent from README's Usage section | **Mismatch/Missing** |
| Web redesign (mature editorial theme) documentation | — | Documented only in `wiki/Home.md` (Hebrew) — not in README.md or CLAUDE.md at all | Missing from the two primary docs (present in wiki) |

### Undocumented Code

- **6 request-body fields** for per-scenario Rule #1 assumptions (`bearExitPeMultiple`,
  `bearRequiredReturnPercent`, `bearMosPercent`, `bullExitPeMultiple`,
  `bullRequiredReturnPercent`, `bullMosPercent`) — `src/web/server.ts:32-37`.
- **Bear/Bull growth-derivation formula** — not documented anywhere: bear growth is
  `effectiveGrowth * 0.75` (or `-3` if `effectiveGrowth <= 0`), bull is `* 1.25` (or `+3`) —
  `src/web/server.ts:113-115,128-130`. This is a real algorithmic decision a future reader
  would want to find in CLAUDE.md, not just in a git log message.
  This is inherently CLI/web-adapter logic, not core `src/valuation/` logic (consistent with
  the existing pattern where adapters own assumption defaults/fallback chains per CLAUDE.md's
  "src/cli/ and src/web/ own the assumption defaults" note) — but it's a case worth deciding
  whether the CLI should eventually offer an equivalent, since right now Bear/Bull scenario
  math is web-only.
- **`ScenarioValuation` interface and the legacy/scenario dual-shape `SavedValuation`** —
  `src/history/types.ts:1-34`.
- **`renderScenarioColumn`/`renderMethodCard`'s per-scenario rendering contract** in `app.js` —
  the `${prefix}-${scenario}-fv`/`-verdict`/`-inputs` DOM id convention that ties HTML to JS is
  undocumented outside the code itself.

### Dead References

None found. No documentation references a file, function, or feature that has been removed —
this project's docs lag behind additions, not removals.

### Configuration Alignment

| Variable | .env.example | CLAUDE.md | Code Usage | Status |
|----------|--------------|-----------|------------|--------|
| `TWELVE_DATA_API_KEY` | Yes (uncommented, required) | Yes (Commands) | `src/data/twelvedata/env.ts:6` | Match |
| `PORT` | Yes (commented, optional) | Yes (Commands) | `src/web/server.ts:19` | Match |
| `CACHE_DIR_PATH` | Yes (commented, optional) | Yes (Gotchas) | `src/data/cache.ts:13` | Match |
| `HISTORY_FILE_PATH` | Yes (commented, optional) | Yes (Gotchas) | `src/history/store.ts:12` | Match |

No gaps in either direction — every `process.env` read in `src/` is documented in both
`.env.example` and CLAUDE.md, and nothing documented goes unused.

### Constants & Weights Verification

| Constant | Documented Value | Code Value | File:Line | Status |
|----------|-------------------|------------|-----------|--------|
| Growth-rate clamp floor | -5% | -5 | `src/valuation/shared/clampGrowthRate.ts:2` | Match |
| Growth-rate clamp cap | 25% | 25 | `src/valuation/shared/clampGrowthRate.ts:3` | Match |
| `mosPercent` valid range | `[0, 100)` | `mosPercent < 0 \|\| mosPercent >= 100` → invalid | `src/valuation/ruleOne/index.ts:48` | Match |
| `mosPercent` default | 0 | `mosPercent: number = 0` | `src/valuation/ruleOne/index.ts:24` | Match |
| Quarterly `income_statement` outputsize | "above 6" (CLAUDE.md:222) | **4** (the actual request value; 6 is a separate ceiling/the annual call's value) | `src/data/twelvedata/client.ts:111` vs. `:123` | Mismatch (see Documentation Accuracy above) |
| Annual `income_statement` outputsize | Not explicitly stated as a distinct value in CLAUDE.md's Gotchas line | 6 | `src/data/twelvedata/client.ts:123` | Needs Review (doc should state this as its own line, separate from the quarterly cap) |
| Cache TTL | 24h | `24 * 60 * 60 * 1000` ms | `src/data/twelvedata/index.ts:74`, `src/data/yahoo/index.ts:31` | Match |
| Web UI MoS dropdown option count (base) | "four-value" (0/10/25/50%) | 4 options, unchanged | `src/web/public/index.html` (`mos-select`) | Match (but doc doesn't mention there are now 3 such dropdowns) |
| Bear scenario growth multiplier | Undocumented | `× 0.75` (or `−3` if growth ≤ 0) | `src/web/server.ts:113-115` | Missing from docs |
| Bull scenario growth multiplier | Undocumented | `× 1.25` (or `+3` if growth ≤ 0) | `src/web/server.ts:128-130` | Missing from docs |
| Bear default Exit P/E / Req. return / MoS | Undocumented | 10 / 15% / 50% | `src/web/server.ts:120-123` | Missing from docs |
| Bull default Exit P/E / Req. return / MoS | Undocumented | 20 / 12% / 10% | `src/web/server.ts:134-137` | Missing from docs |

### Test Coverage Gaps

| Module/Feature | Has Tests | Notes |
|----------------|-----------|-------|
| `src/valuation/lynch/`, `src/valuation/ruleOne/`, `src/valuation/shared/clampGrowthRate.ts` | Yes | Full coverage, all match documented behavior |
| `src/data/twelvedata/*` (client, normalize, historicalPe, index) | Yes | Full coverage |
| `src/data/yahoo/*` (client, index) | Yes | Full coverage |
| `src/data/cache.ts` | Yes | Covered |
| `src/data/twelvedata/env.ts` | **No** | Only ever mocked out (`index.test.ts:15`) — the real throw-if-missing validation logic is never directly exercised |
| `src/history/store.ts` | **Partial** | `index.test.ts` always passes an explicit `filePath` override, so `resolveHistoryFilePath`'s `HISTORY_FILE_PATH`-env-var and default-path branches (`store.ts:10-14`) are never hit |
| `src/web/server.ts` | Yes, including the recent fix | The new bear/bull-uses-real-user-input regression test exists (`server.test.ts:130-178`) |
| `src/cli/index.ts`, `src/cli/formatOutput.ts` | Yes | Covered, including the `r.base ?? r` legacy/new dual-shape read added this session |
| `src/web/public/app.js` — `renderHistoryTable` | **No** | Zero coverage of the legacy-vs-3-scenario branching (`item.base ? [...] : [...]`) or the `rowSpan` logic for multi-scenario rows — the most structurally complex function in the file, and not even exported by the current test harness (`app.test.js:70` only returns `{ formatStockDataError, renderAnalystTable }`) |
| `src/history/` — `ScenarioValuation`/`base`/`bear`/`bull` persistence | **No** | `index.test.ts` only constructs legacy-flat-shaped records (zero matches for `base`/`bear`/`bull`/`ScenarioValuation` in the test file); no test confirms a scenario-shaped record round-trips correctly through save/read/filter |

### Recommendations

1. **Update CLAUDE.md's Architecture and Web REST surface sections** to document the
   3-scenario feature: the nested `{base,bear,bull}` response shape, all 14
   `ValuateRequestBody` fields (not just 3), the bear/bull growth-derivation formula and
   default assumption values, and the now-3-dropdown MoS UI. This is the single highest-value
   fix — it's the largest and most recent gap, and CLAUDE.md is the file loaded automatically
   every session, unlike the wiki.
2. **Update CLAUDE.md's History section** to describe the legacy/`base`/`bear`/`bull` dual
   shape in `SavedValuation`, and why `formatHistoryOutput` reads `r.base ?? r`.
3. **Fix the outputsize sentence in CLAUDE.md's Gotchas** (line 222) to correctly attribute
   `outputsize=4` to the quarterly call and `outputsize=6` to the annual call/plan-tier
   ceiling, instead of the current sentence that reads as if quarterly itself uses 6.
4. **Add `-m/--mos` and `-n/--notes` to README.md's Usage section** — both are real, working
   flags with zero documentation footprint currently.
5. **Add test coverage for `renderHistoryTable`'s legacy-vs-scenario branching and `rowSpan`
   logic** — this is the newest, most complex, and (per this session's own fix commit) most
   recently-buggy code path in the frontend, and it currently has none. At minimum, widen
   `app.test.js`'s harness export to include `renderHistoryTable` and add cases for: a legacy
   record, a full base/bear/bull record, and a record with `base` but missing `bear`/`bull`
   (the `item.bear || item.base` fallback path).
6. **Add a `src/history/` test that round-trips a `base`/`bear`/`bull`-shaped record** through
   `saveValuation`/`getHistory` to confirm the new shape persists and filters correctly, not
   just that it type-checks.
7. **Optional/low-priority**: reconcile `yahoo/`'s "nothing outside may import `client.ts` or
   `types.ts`" wording in CLAUDE.md with the reality that `types.ts` is intentionally imported
   by `cache.ts` and test files for shared type shapes — either loosen the doc's wording to
   exempt `types.ts` (matching how the `twelvedata/` paragraph is already worded), or make the
   exception explicit rather than silent.
8. **Optional**: since `CURRENT_WORK.md` already documents the 3-scenario feature accurately
   and in detail, a fast path to fixing findings 1–2 above is to port that existing writeup
   into CLAUDE.md's Architecture section rather than re-deriving it from scratch.
