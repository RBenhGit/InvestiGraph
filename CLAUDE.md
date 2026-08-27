# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project: Eps_Evaluation

EPS×multiple stock valuation tool. Fetches fundamentals from the Twelve Data API and computes
two independent "fair value" estimates from EPS × growth rate — Lynch/PEG-style and a Rule
#1-style discounted exit multiple — exposed via both a CLI and a small web UI.

## Commands

- Build: `npm run build` (`tsc -p tsconfig.json`)
- Test (all): `npm test` (`vitest run`) — **cannot be run from `Z:` (EPERM); run it over SSH,
  see Gotchas:** `ssh aviv@100.76.172.46 'cd ~/shared_disk/Cursor_apps/Eps_Evaluation && npm test'`
- Test (single): `npx vitest run <path>` (same `Z:` limitation — same SSH hop)
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
`src/web/`). Both adapters call the `twelvedata` entry point to collect fundamentals. The web
adapter always additionally calls `yahoo` for analyst data. The CLI only calls `yahoo`
conditionally — when `StockData.staleTtmWarning` is true (see `src/data/resolveEps.ts`) — to try
to replace a stale Twelve Data `epsTtm` with Yahoo's `trailingEps`; a healthy ticker never
triggers the extra network call.

```
src/data/cache.ts       saveCached*/getCached* — disk-backed cache, shared by twelvedata/ and yahoo/
src/data/resolveEps.ts  resolveEpsWithFallback(data, analystConsensus) -> ResolvedEps — Yahoo fallback for stale Twelve Data epsTtm
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

**`src/data/resolveEps.ts`** — a pure function (`resolveEpsWithFallback`), sibling of
`twelvedata/`/`yahoo/` like `cache.ts` above, imported by both `cli/index.ts` and `server.ts` so
their behavior can't drift (see the growth-fallback-chain incident this file already warns about
elsewhere). Only relevant when `StockData.staleTtmWarning` is true — Twelve Data's
quarterly `income_statement` has been observed lagging a real earnings release by 10+ days with no
error, no warning (see the CSCO incident in `CURRENT_WORK.md`'s "Known problems"). When triggered,
tries Yahoo's `AnalystConsensus.trailingEps` (a ready-made TTM figure — Yahoo's own per-quarter
data is either deprecated/incomplete or Non-GAAP, so no per-quarter splice is possible) as a
whole-figure replacement. Returns one of three `EpsSource` values
(`'twelvedata'`/`'yahoo-fallback'`/`'twelvedata-stale-no-fallback'`) plus a human-readable
`detail` string — never silently substitutes a number without saying where it came from. A
healthy (non-stale) ticker never triggers the extra Yahoo call.

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
with a typed `ValuationError`, never a throw. **The two methods do NOT share an identical guard
set**: `calculateLynchValue` additionally rejects a non-positive growth rate with
`NEGATIVE_GROWTH_RATE`, because `EPS x growth%` is a PEG-style heuristic defined only for a
growing company — with a negative rate it returns a negative *dollar* figure, which is not a
cheap valuation but a meaningless one (real case: ABBV's -29.03% 3y CAGR clamped to -5% yielded
a "fair value" of -17.69, shown by both adapters as legitimate until this was caught). Rule #1
is unaffected and still returns a sane number, since compounding a positive EPS at a negative
rate shrinks it without flipping the sign. Consequence for callers: `ruleOne` is the more
permissive method, so `lynch.ok` does **not** imply `ruleOne.ok` and vice versa — code that
falls back from one to the other must not assume they fail together. `calculateRuleOneValue` additionally takes an
optional `mosPercent` (Margin of Safety, default `0`) that discounts the sticker price down to
a target buy price (`fairValue = stickerPrice * (1 - mosPercent / 100)`); the function itself
accepts any value in `[0, 100)` (`INVALID_MOS` otherwise) — the web UI's four-value MoS
dropdown (0/10/25/50%) is a UI-level convention, not a constraint enforced by the function or
by the CLI's free-text `-m/--mos <percent>` flag. MoS is a single value shared across all three
scenarios (see "Bear/Base/Bull scenarios" below) — there is no per-scenario MoS override.

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
uses exactly the request's own `growthRatePercent`/`exitPeMultiple`/`requiredReturnPercent`
(the CLI-equivalent inputs). **Growth, exit-P/E, and required-return are all independently
editable per scenario** — the web UI's 3-row `scenario-assumptions` table
(`src/web/public/index.html`) gives Bear/Base/Bull each their own Growth/Exit P/E/Req. return
inputs, sent as `bearGrowthRatePercent`/`bearExitPeMultiple`/`bearRequiredReturnPercent` and
the `bull*` equivalents. **MoS is the one exception — a single value shared across all three
scenarios**, set once in the top assumptions row (`mosPercent`) and applied identically to
base/bear/bull; there is no `bearMosPercent`/`bullMosPercent`. Bear/bull growth falls back to
being derived from the base scenario's `effectiveGrowth` (`* 0.75` for bear, `* 1.25` for bull,
or `-3`/`+3` when `effectiveGrowth <= 0`) only when the request omits
`bearGrowthRatePercent`/`bullGrowthRatePercent` entirely (e.g. an older client); exit-P/E and
required-return likewise only fall back to fixed defaults (bear: 10 / 15%, bull: 20 / 12%) when
their fields are omitted — **none of these must ever be hardcoded when the field is present**,
since that previously shipped as a real bug (server ignored the user's own bear/bull inputs
entirely), caught and fixed with a regression test (`src/web/server.test.ts`, "uses the
bear/bull growth, exit-P/E, and required-return the user actually provided, not hardcoded
defaults"). The CLI has no equivalent — it only ever computes the single base scenario.

**CLI flags** (`src/cli/index.ts`): `-m/--mos <percent>` (Margin of Safety, see above),
`-n/--notes <text>` (thesis attached to a saved valuation), `-s/--save` (save the result to
history), `-H/--history [ticker]` (print saved valuations, optionally filtered by ticker).

**Web REST surface** (`src/web/server.ts`): `POST /api/valuate` body —
`ticker` (required), `epsOverride?`, `growthRatePercent?`, `exitPeMultiple`,
`requiredReturnPercent`, `years`, `mosPercent?` (shared by all three scenarios),
`bearGrowthRatePercent?`, `bearExitPeMultiple?`, `bearRequiredReturnPercent?`,
`bullGrowthRatePercent?`, `bullExitPeMultiple?`, `bullRequiredReturnPercent?`,
`forceRefresh?` — see "Bear/Base/Bull scenarios" above. Also `GET /api/history?ticker=`,
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
  plan (HTTP 400 above it) — confirmed live. Both the quarterly and annual calls in `client.ts`
  request the full `outputsize=6` the plan allows (the quarterly call used to request only 4 —
  all `resolveTtmEps`'s net-income fallback needs — but was bumped to 6 so
  `calculateTtmEpsGrowthPercent`, added 2026-08-26, gets as many quarters as this plan tier can
  supply; it still needs 8 for a true year-over-year TTM comparison and correctly returns `null`
  rather than approximate from fewer — see `StockData.growth.epsTtmGrowthPercent`).
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
- **Tests/build/lint cannot run from the `Z:` drive, and file edits (Edit/Write tools, `mkdir`,
  even Node's own `fs.mkdirSync`) can fail on it too — do both over SSH instead.** `Z:` is a
  Windows SSHFS mount of the very same filesystem the project lives on (see CURRENT_WORK.md's
  "Known problems"); its driver returns `EPERM` instead of `EEXIST` when something calls
  `mkdir` on an existing directory. This breaks vitest at startup
  (`EPERM: operation not permitted, mkdir 'node_modules/.vite-temp'`) — `TMPDIR` does not help
  (Vite derives that path from the project root) and `npx vitest` fails identically — **and it
  also breaks editing an existing file** (confirmed 2026-08-27: both the Edit tool and a bare
  `fs.mkdirSync(existingDir, {recursive: true})` throw the same `EPERM` on a directory that
  already exists, for any file, not just ones under `node_modules`). It is intermittent per
  directory/session, not a hard rule for every path, but treat any `EPERM: ... mkdir` while
  editing on `Z:` as this same issue rather than investigating from scratch. Because it is the
  same filesystem, there is nothing to copy — SSH in and run/edit in place. For tests/build/lint:

  ```bash
  ssh aviv@100.76.172.46 'cd ~/shared_disk/Cursor_apps/Eps_Evaluation && npm test'
  ```

  For a file edit that hits the same `EPERM`, editing in place with `sed`/a heredoc, or `scp`-ing
  a small Python/Node script and running it over the same SSH hop, both work — write the
  replacement as a whole-file or exact-string substitution to avoid quoting issues over SSH.

  Host details: user `aviv`, Tailscale `100.76.172.46`, Ubuntu 26.04 LTS, Node v24.15.0,
  npm 11.17.0, key-based auth already in `~/.ssh/config` (`StrictHostKeyChecking no`). The LAN
  address `192.168.1.224` appears in `ip addr` on that box but **port 22 there times out from
  this machine — always use the Tailscale address**. `.claude/hooks/stop-test-gate.sh` already
  routes its `TEST_CMD` through this same hop (commit `0d6082b`). Verified 2026-08-27:
  228 tests across 16 files, all passing.
