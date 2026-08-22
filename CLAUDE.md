# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project: Eps_Evaluation

EPS×multiple stock valuation tool. Fetches fundamentals from the Twelve Data API and computes
two independent "fair value" estimates from EPS × growth rate — Lynch/PEG-style and a Rule
#1-style discounted exit multiple — exposed via both a CLI and a small web UI.

## Commands

- Build: `npm run build` (`tsc -p tsconfig.json`)
- Test (all): `npm test` (`vitest run`)
- Test (single): `npx vitest run <path>`
- Lint: `npm run lint` (`eslint .`)
- Format: `npm run format` (`prettier --write .`)
- Run locally: `npm run cli -- TICKER` (e.g. `npm run cli -- AAPL`), `npm run web` (Fastify on `PORT`, default 3210 — chosen to avoid colliding with other local projects on 3000/3001/3100)

Requires `TWELVE_DATA_API_KEY` in `.env` (copy from `.env.example`) for both `cli` and `web` to
fetch live data. There is a disk-backed cache (`src/data/cache.ts`, see Architecture below) that
serves stale-but-present data when the live API call fails, so a missing/invalid key or an
outage doesn't always mean total failure if a prior successful lookup for that ticker was
cached — but there is no seeded/mocked data shipped with the repo, so a ticker never looked up
before still requires a live key.

## Architecture

Two shared core layers (`src/data/`, `src/valuation/`) sit behind thin adapters (`src/cli/`,
`src/web/`). While both adapters call the `twelvedata` entry point to collect fundamentals, the
web adapter additionally calls `yahoo` for analyst data. The CLI does not use the `yahoo` module.

```
src/data/cache.ts       saveCached*/getCached* — disk-backed cache, shared by twelvedata/ and yahoo/
src/data/twelvedata/   fetchStockData(ticker, opts?) -> StockDataResult   (external API -> StockData)
src/data/yahoo/        fetchAnalystConsensus(ticker, opts?) -> AnalystConsensusResult
src/history/            saveValuation/getHistory/deleteValuation -> HistoryResult   (disk-backed persistence)
src/valuation/lynch/    calculateLynchValue(eps, growth) -> ValuationResult
src/valuation/ruleOne/  calculateRuleOneValue(eps, growth, exitPe, requiredReturn, years, mosPercent?) -> ValuationResult
src/cli/                thin wrapper: calls fetchStockData + both valuations, formats to stdout
src/web/                Fastify server: POST /api/valuate does the same, serves src/web/public/
```

**`src/data/twelvedata/`** — `index.ts` is the _only_ published entry point
(`fetchStockData`); nothing outside this directory may import `client.ts`, `normalize.ts`,
`historicalPe.ts`, or `env.ts` directly (stated at the top of `index.ts`). Internally:

- `client.ts` — raw `fetch` calls against Twelve Data's REST endpoints (`quote`, `statistics`,
  `growth_estimates`, `income_statement` quarterly/annual, `time_series` monthly). Returns
  parsed JSON as-is, still carrying Twelve Data's string-typed numeric fields.
- `normalize.ts` — pure helpers, no network/imports from `client.ts`: `parseNumber` (treats a
  real `0` as a value, not "missing" — a named regression guard), `resolveTtmEps` (prefers the
  API's point-in-time EPS, falls back to net-income-from-quarters when it's missing/zero),
  `assertNonEmpty`/`TwelveDataResponseError` (a 200 status isn't proof of usable data),
  `validateCurrency`/`CurrencyMismatchError`, `calculateCagrPercent`.
- `historicalPe.ts` — computes trailing 1y/3y/5y median P/E locally from annual EPS +
  monthly closes, since Twelve Data has no such field. Requires `ceil(N/2)` valid points per
  window. (Note: output fields are named `avg1y`/`avg3y`/`avg5y` for historical reasons).
- `env.ts` — the single read point for `TWELVE_DATA_API_KEY`; nothing else should read
  `process.env.TWELVE_DATA_API_KEY` directly.
- `index.ts` orchestrates: fetches everything in parallel (`growth_estimates` alone is
  `.catch()`-guarded — it 403s on non-Enterprise API keys and must degrade to `null`, not fail
  the whole lookup), resolves TTM EPS, cross-checks price vs. fundamentals currency, and returns
  a discriminated-union `StockDataResult` (`{ ok: true, data }` or `{ ok: false, error }` with a
  typed `StockDataError`) rather than throwing to callers.

**`src/data/yahoo/`** — `index.ts` is the _only_ published entry point (`fetchAnalystConsensus`);
`client.ts` is never imported outside this directory. `types.ts` is the one intentional
exception — `src/data/cache.ts` and test files import `AnalystConsensus` from it directly
(`import type { AnalystConsensus } from './yahoo/types'`) for shared type shapes; this is a
type-only import, not a dependency on the module's implementation, so it doesn't violate the
sole-entry-point principle the way importing `client.ts` would. Internally uses
`yahoo-finance2` to fetch analyst consensus (next-year EPS growth, price targets, recommendations)
plus three "financial health" reference fields: `beta` and `priceToSales` are read straight from
Yahoo's `summaryDetail` module (no local math); `ruleOf40 = (revenueGrowth + ebitdaMargins) * 100`
is computed locally — both `revenueGrowth` and `ebitdaMargins` arrive from Yahoo as fractions
(e.g. `0.852`, not `85.2`), so the single `* 100` is correct, not a double-conversion (hand-
verified live against NVDA: `0.852 + 0.65294 = 1.50494 → 150.494`, a genuinely high but real
score for that company's growth/margin profile at the time — don't "fix" a high Rule of 40
result without re-checking the raw Yahoo fields first; it looked like a units bug on first
glance and wasn't one). All three fields are `number | null`, never
`undefined` — UI code checking for their presence must test `!== null`, not `!== undefined`
(`app.js`'s "Financial Health" section header had exactly this bug: `!== undefined` is always
true for a typed-`null` field, so the header rendered even when both were `null`).
**Important Rule**: This module uses a public endpoint and does not require an API key (hence its
absence from `.env.example`). Furthermore, any failure here MUST gracefully degrade to returning
`null` (never failing the overall valuation request), as it's an auxiliary data source.

**`src/data/cache.ts`** — a disk-backed cache shared by both `twelvedata/index.ts` and
`yahoo/index.ts` (imported as a sibling, `../cache`; it is not internal to either module). Plain
JSON files under `cache/` (`twelvedata_<TICKER>.json` / `yahoo_<TICKER>.json`), directory
overridable via the optional `CACHE_DIR_PATH` env var. All cache I/O failures are silently
swallowed by design — caching must never fail the user's actual request. Both `fetchStockData`
and `fetchAnalystConsensus` now take an optional second `{ forceRefresh?, maxAgeMs? }` options
argument: on a normal call they read-through the cache (24h TTL, no network call at all if
fresh); on a live-fetch failure they fall back to serving stale cached data instead of failing,
which is the behavior described in the Commands section above. The web UI's "🔄 Refresh Live"
button and the `forceRefresh` field on `POST /api/valuate` bypass the cache to force a live call.

**`src/history/`** — `index.ts` is the published entry point (`saveValuation`, `getHistory`,
`deleteValuation`, plus the shared types); `store.ts` is internal-only (raw JSON-array file I/O
against `history.json`, directory/path overridable via the optional `HISTORY_FILE_PATH` env
var) and is never imported outside this directory. Same `{ ok }`-result convention as the rest
of the codebase (`HistoryResult<T>`, `HistoryError` of `IO_ERROR`/`NOT_FOUND`/`INVALID_INPUT`).
Lets a user save a computed valuation and retrieve/filter/delete it later. Wired into
`POST/GET /api/history` and `DELETE /api/history/:id` on the web side, and `-s/--save`,
`-H/--history [ticker]` on the CLI.

`SavedValuation` (`src/history/types.ts`) has two coexisting shapes, both optional, for backward
compatibility: **legacy flat fields** (`growthRatePercent`, `exitPeMultiple`,
`requiredReturnPercent`, `mosPercent`, `lynchFairValue`, `ruleOneFairValue`) written by the
CLI's `--save`, and **new nested fields** `base?/bear?/bull?: ScenarioValuation` (each holding
the same six fields per scenario) written by the web UI's 3-scenario save (see "Bear/Base/Bull
scenarios" below). A single record only ever has one shape or the other, never both. Any code
that reads a saved valuation's fair-value/assumption fields must resolve `record.base ?? record`
first, then read from that — `src/cli/index.ts`'s `formatHistoryOutput` does this so the
`-H/--history` table renders correctly for records saved by either adapter/era.

**`src/valuation/`** — pure functions, no I/O. `shared/clampGrowthRate.ts` clamps every growth
rate to `[-5%, 25%]` before either method uses it (both `lynch` and `ruleOne` call it
internally — callers pass the raw, unclamped rate). Both `calculateLynchValue` and
`calculateRuleOneValue` accept `epsTtm`/`growthRatePercent` as `number | null | undefined`
(they flow in directly from `StockData`'s independently-nullable growth fields) and return a
`ValuationResult`: `{ ok: true, fairValue, inputs, intermediate? }` or `{ ok: false, error }`
with a typed `ValuationError`, never a throw. `calculateRuleOneValue` additionally takes an
optional `mosPercent` (Margin of Safety, default `0`) that discounts the sticker price down to
a target buy price (`fairValue = stickerPrice * (1 - mosPercent / 100)`); the function itself
accepts any value in `[0, 100)` (`INVALID_MOS` otherwise) — the web UI's four-value dropdowns
(0/10/25/50%, one per scenario — see "Bear/Base/Bull scenarios" below) are a UI-level
convention, not a constraint enforced by the function or by the CLI's free-text
`-m/--mos <percent>` flag (which only ever sets the single base-scenario value the CLI computes).

**Error handling convention**: both layers use `{ ok: boolean }` discriminated-union results
end-to-end instead of exceptions crossing module boundaries — `src/cli/index.ts` and
`src/web/server.ts` both just switch on `result.ok`.

**`src/cli/`** and **`src/web/`** own the assumption defaults (exit P/E, required return,
years) and the growth-rate fallback chain (`analystEstimate5y ?? historical3y ?? historical1y`)
— deliberately kept out of `src/valuation/` so those functions stay pure and take every input
explicitly. The web UI additionally lets the user override growth/exit-PE/required-return/years
per request instead of using the CLI's fixed defaults. **The fallback chain must stay
byte-identical between `cli/index.ts` and `server.ts`** — it silently diverged once (an
undocumented `Math.min(hist, 15)` cap and a default-to-`0` on the web side, neither in the CLI,
neither tested) and produced fair values differing by up to ~47% between the two adapters for
identical data before being caught and removed; when all growth sources are `null`, the correct
behavior is to leave `effectiveGrowth` as `null` and let `calculateLynchValue`/
`calculateRuleOneValue` return `MISSING_GROWTH_RATE` — never default to `0`, which produces a
fabricated-but-`ok:true` $0 fair value with no error shown.

**Bear/Base/Bull scenarios** (web only — `src/web/server.ts`): every `POST /api/valuate`
computes all three scenarios for both methods in one request, returning `lynch`/`ruleOne` as
`{ base, bear, bull }` (each a full `ValuationResult`) instead of a single flat result. Base
uses exactly the request's own `growthRatePercent`/`exitPeMultiple`/`requiredReturnPercent`/
`mosPercent` (the CLI-equivalent inputs). Bear and bull growth are **auto-derived** from the
base scenario's `effectiveGrowth` — never a separate growth input — as `effectiveGrowth * 0.75`
for bear and `* 1.25` for bull (or `-3`/`+3` respectively when `effectiveGrowth <= 0`, since a
multiplier does nothing useful on a non-positive rate). Bear/bull's exit-P/E, required-return,
and MoS are **not** auto-derived — they come from their own dedicated request-body fields
(`bearExitPeMultiple`, `bearRequiredReturnPercent`, `bearMosPercent`, `bullExitPeMultiple`,
`bullRequiredReturnPercent`, `bullMosPercent`), which the web UI's 3-row `scenario-assumptions`
table lets the user edit independently per scenario (`src/web/public/index.html`) — **these
must never be hardcoded on the server**; they were once (10/15/50 for bear, 20/12/10 for bull,
silently ignoring whatever the user typed), which produced correct-looking but wrong fair values
for any user who changed an assumption expecting it to apply everywhere, and was fixed with a
regression test (`src/web/server.test.ts`, "uses the bear/bull exit-P/E, required-return, and
MoS the user actually provided, not hardcoded defaults"). Only `?? <default>` fallbacks for
clients that omit the fields entirely: bear defaults to exit P/E 10 / req. return 15% / MoS 50%,
bull to exit P/E 20 / req. return 12% / MoS 10%. The CLI has no equivalent — it only ever
computes the single base scenario.

**CLI flags** (`src/cli/index.ts`): `-m/--mos <percent>` (Margin of Safety, see above),
`-n/--notes <text>` (thesis attached to a saved valuation), `-s/--save` (save the result to
history), `-H/--history [ticker]` (print saved valuations, optionally filtered by ticker).

**Web REST surface** (`src/web/server.ts`): `POST /api/valuate` body —
`ticker` (required), `epsOverride?`, `growthRatePercent?`, `exitPeMultiple`,
`requiredReturnPercent`, `years`, `mosPercent?`, `bearExitPeMultiple?`,
`bearRequiredReturnPercent?`, `bearMosPercent?`, `bullExitPeMultiple?`,
`bullRequiredReturnPercent?`, `bullMosPercent?`, `forceRefresh?` — see "Bear/Base/Bull
scenarios" above for the six `bear*`/`bull*` fields. Also `GET /api/history?ticker=`,
`POST /api/history`, `DELETE /api/history/:id`.

## Principles

### 0. Think before coding

- State assumptions explicitly. If uncertain, ask rather than guess.
- When a request is ambiguous, present the interpretations — don't silently pick one.
- Push back when a simpler approach exists, before implementing the one requested.
- When confused, stop and name what's unclear. A wrong assumption costs more than a question.

### 1. Simplicity

- Prefer the design a reader can hold in one read.
- No abstraction until variation is real; no generalization before behaviors truly share a core.
- No speculative flags, layers, or config. Optimize only against a measured budget.

### 2. Modularity

- One concern per module. Structure: domain directories containing vertical slices
  (e.g. `<domain>/<use-case>/` holding handler, validation, and its tests together).
- Depend on published interfaces only — never reach into another module's internals.
- A change should touch one slice and its tests. If it can't, say so before implementing.

### 3. Surgical changes

- Touch only what the task requires. Clean up only your own mess.
- Don't refactor unbroken adjacent code or "improve" what you happened to read.
- Match the existing style, even where you'd have chosen differently.
- Only remove dead code that your own change created.

## Verification policy

- Every change ends with its check passing: run the test command from **Commands** above
  (or the relevant single test) and show the output. If you can't verify it, don't call it done.
- Fix root causes. Never suppress an error, skip a test, or weaken an assertion to get green.
- For bug fixes: write a failing test that reproduces the issue first, then fix it.
- Performance work needs a stated budget and a measurement before any change (`perf-investigator`).
  "Faster" is not a budget, and an unmeasured optimization is just added complexity.

## Workflow

- Non-trivial changes (multi-file, unfamiliar code, uncertain approach): explore and plan
  first; skip planning for one-line fixes.
- Large features: `/spec` (interview → SPEC.md), then `/slice` (→ TASKS.md), then one task per
  fresh context via the `task-implementer` agent. Don't implement a feature nobody has scoped.
- For risky or multi-session work, start from a worktree on a new branch and confirm the
  suite is green BEFORE the first edit — then any later failure is attributable to this change.
- Before treating a feature as done, review the diff against the plan in a fresh context
  (`code-reviewer` agent or `/code-review`). Escalate when the change earns it:
  `architecture-reviewer` if it crosses module lines or adds a layer, `security-auditor` if it
  touches input handling, auth, files, shell, or dependencies.
- Commit with a descriptive message after each completed unit of work.

## Session log

`CURRENT_WORK.md` is the running work log for this project: what's done, what's in flight,
known problems, what's next. **Read it at the start of every session, before doing anything
else** — that's how continuity across sessions works without re-explaining context each time.
Update it whenever you plan, execute, or hit a problem: after finishing a unit of work, before
ending a session, and any time state changes enough that the next session would be misled by
a stale file. Never leave "In flight" pointing at something already finished or abandoned.

## Multi-session projects

Start every session with `/orient`: read git log + CURRENT_WORK.md, verify the baseline is
green, pick ONE feature, state the finish line. A red baseline is the session's work — don't
build on it. Complete one feature at a time. Leave the code mergeable — no half-done work
without a note in CURRENT_WORK.md. Run `/harness` once at the start of a project that will
span many sessions.

## Repository etiquette

- Branch naming: `feature/<slug>`, `fix/<slug>`
- Commit messages: imperative mood, one logical change per commit

## Gotchas

- `growth_estimates` is gated behind Twelve Data's higher plan tiers — a non-Enterprise key
  gets a 403 there while every other endpoint succeeds. `fetchStockData` swallows that failure
  (`.catch(() => null)`); don't let a future change turn it back into a hard failure.
- The `income_statement` endpoint has a hard ceiling of `outputsize=6` below the Enterprise
  plan (HTTP 400 above it) — confirmed live. The quarterly call in `client.ts` deliberately
  requests only `outputsize=4` (that's all `resolveTtmEps`'s net-income fallback needs), well
  under the ceiling; the annual call requests the full `outputsize=6` the plan allows.
  `historicalPe` needs 7+ quarters for even a 1y average, so on a lower-tier key
  `historicalPe` will always come back all-null via the quarterly path — that's a plan-tier
  limit, not a bug (which is why `historicalPe.ts` computes its P/E points from the annual
  series instead, one point per fiscal year, not from quarterly data at all).
- Twelve Data returns numeric fields as strings inconsistently; always go through
  `normalize.ts#parseNumber` rather than `Number(...)` or truthiness checks — a real `0` (e.g.
  breakeven EPS) must not be treated as missing.
- Ports 3000/3001/3100 are already used by other local projects on this machine; the web
  server's default is 3210 for that reason — don't "fix" it back to 3000.
- `CACHE_DIR_PATH` and `HISTORY_FILE_PATH` (`src/data/cache.ts`, `src/history/store.ts`) are
  optional env vars with safe defaults (`cache/` and `history.json` under the project root) —
  listed commented-out in `.env.example` the same way `PORT` is; almost nobody needs to set them.
