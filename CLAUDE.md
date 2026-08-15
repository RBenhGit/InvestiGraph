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

Requires `TWELVE_DATA_API_KEY` in `.env` (copy from `.env.example`) for both `cli` and `web` —
neither has a mocked/offline mode.

## Architecture

Two shared core layers (`src/data/`, `src/valuation/`) sit behind thin adapters (`src/cli/`,
`src/web/`). Both adapters call the same two entry points and differ only in how they collect
inputs and render output.

```
src/data/twelvedata/   fetchStockData(ticker) -> StockDataResult   (external API -> StockData)
src/valuation/lynch/    calculateLynchValue(eps, growth) -> ValuationResult
src/valuation/ruleOne/  calculateRuleOneValue(eps, growth, exitPe, requiredReturn, years) -> ValuationResult
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
- `historicalPe.ts` — computes trailing 1y/3y/5y average P/E locally from quarterly EPS +
  monthly closes, since Twelve Data has no such field (only point-in-time `trailing_pe`).
- `env.ts` — the single read point for `TWELVE_DATA_API_KEY`; nothing else should read
  `process.env.TWELVE_DATA_API_KEY` directly.
- `index.ts` orchestrates: fetches everything in parallel (`growth_estimates` alone is
  `.catch()`-guarded — it 403s on non-Enterprise API keys and must degrade to `null`, not fail
  the whole lookup), resolves TTM EPS, cross-checks price vs. fundamentals currency, and returns
  a discriminated-union `StockDataResult` (`{ ok: true, data }` or `{ ok: false, error }` with a
  typed `StockDataError`) rather than throwing to callers.

**`src/valuation/`** — pure functions, no I/O. `shared/clampGrowthRate.ts` clamps every growth
rate to `[-5%, 25%]` before either method uses it (both `lynch` and `ruleOne` call it
internally — callers pass the raw, unclamped rate). Both `calculateLynchValue` and
`calculateRuleOneValue` accept `epsTtm`/`growthRatePercent` as `number | null | undefined`
(they flow in directly from `StockData`'s independently-nullable growth fields) and return a
`ValuationResult`: `{ ok: true, fairValue, inputs, intermediate? }` or `{ ok: false, error }`
with a typed `ValuationError`, never a throw.

**Error handling convention**: both layers use `{ ok: boolean }` discriminated-union results
end-to-end instead of exceptions crossing module boundaries — `src/cli/index.ts` and
`src/web/server.ts` both just switch on `result.ok`.

**`src/cli/`** and **`src/web/`** own the assumption defaults (exit P/E, required return,
years) and the growth-rate fallback chain (`analystEstimate5y ?? historical3y ?? historical1y`)
— deliberately kept out of `src/valuation/` so those functions stay pure and take every input
explicitly. The web UI additionally lets the user override growth/exit-PE/required-return/years
per request instead of using the CLI's fixed defaults.

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
- The `income_statement` endpoint rejects `period=quarterly&outputsize` above 6 below the
  Enterprise plan (HTTP 400). `historicalPe` needs 7+ quarters for even a 1y average, so on a
  lower-tier key `historicalPe` will always come back all-null — that's a plan-tier limit, not
  a bug.
- Twelve Data returns numeric fields as strings inconsistently; always go through
  `normalize.ts#parseNumber` rather than `Number(...)` or truthiness checks — a real `0` (e.g.
  breakeven EPS) must not be treated as missing.
- Ports 3000/3001/3100 are already used by other local projects on this machine; the web
  server's default is 3210 for that reason — don't "fix" it back to 3000.
- No mocked/offline mode: both `npm run cli` and `npm run web` require a live
  `TWELVE_DATA_API_KEY` in `.env` to do anything.
