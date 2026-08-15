# Current Work — Eps_Evaluation

**Updated:** 2026-08-15

## Where things stand

EPS×multiple stock valuation tool — Node.js + TypeScript, shared core (`src/data/`,
`src/valuation/`) with thin CLI (`src/cli/`) and web (`src/web/`) adapters. Fully implemented,
end-to-end checked against the live Twelve Data API. **67/67 tests, `npm run lint` clean,
`npm run build` (tsc) clean.** Web UI redesign (below) verified live against the API and in a
real browser — ready to commit.

## Last completed

Implemented the whole app in one pass (tasks 1-9 of
`/home/aviv/.claude/plans/request-interrupted-by-user-mutable-blanket.md`):

- **Data layer** (`src/data/twelvedata/`): `fetchStockData(ticker)` -- the single published
  entry point. Pulls quote, statistics, growth_estimates, quarterly/annual income statements,
  and monthly time series from Twelve Data; normalizes with guards against falsy-zero EPS,
  empty-but-200 responses, and currency mismatches. Includes average P/E over trailing
  1y/3y/5y (`historicalPe`), computed locally since the provider has no such field -- confirmed
  live, only `trailing_pe`/`forward_pe` point-in-time values exist (now surfaced separately as
  `providerReference`, reference-only, never fed into either valuation).
- **Valuation layer** (`src/valuation/`): pure functions, `calculateLynchValue` (PEG-style, no
  discounting) and `calculateRuleOneValue` (EPS projection x exit multiple, discounted once --
  still not DCF). Growth rate clamped to [-5%, 25%] before use in both.
- **CLI** (`src/cli/index.ts` + `formatOutput.ts`): `npm run cli -- TICKER`.
- **Web** (`src/web/server.ts` + `public/`): `npm run web` (Fastify, `PORT` default 3210).
- Wired `CLAUDE.md`'s Commands section and the `post-edit.sh`/`stop-test-gate.sh` hooks to the
  real npm scripts. The protected-paths list needed no change -- the API-key secrets file and
  the npm lockfile were already covered by its defaults.

**Task 10 -- end-to-end sanity check**, against the real Twelve Data API, surfaced two live
plan-tier issues -- both fixed and covered by tests:

- `growth_estimates` 403s on non-Enterprise API keys -> `fetchStockData` now catches that and
  degrades `historical5yPercent`/`analystEstimate5yPercent` to `null` instead of failing the
  whole lookup.
- `income_statement?period=quarterly` rejects `outputsize` above 6 below Enterprise -> dropped
  to 4 (the actual minimum needed for TTM EPS). `historicalPe` will read all-null on this key
  tier -- expected, not a bug.
- Also fixed while at it: web server default port 3000 -> 3210 (collided with other local
  projects) and now binds `0.0.0.0` instead of loopback-only.

Committed as `7821413`. `CLAUDE.md` was also expanded with an Architecture section and a real
Gotchas list -- see that commit too.

**Web UI redesign** -- reorganized `src/web/public/{index.html,app.js,style.css}` per user
feedback (a screenshot showed a flat, hard-to-scan stat strip missing several already-fetched
fields). No backend/data changes -- `StockData` already carried everything needed. Added:

- A **price banner** at the top of results: current price + EPS(TTM), with both fair values
  shown immediately beside it as **% upside/downside vs. current price** -- previously you had
  to read two separate cards and do that math yourself.
- A **growth-rate sources panel**: all four growth figures (1Y historical, 3Y CAGR, 5Y
  historical, Analyst 5Y estimate) listed together with the one in use highlighted. Previously
  the non-selected chip values disappeared once you picked one.
- A **valuation multiples panel**: historical avg P/E (1y/3y/5y) + trailing P/E + PEG grouped
  together, explicitly labeled reference-only.

Verified: 67/67 tests, lint clean, build clean, and live-checked in a browser via SSH port
forward against MSFT — price banner, growth panel, and multiples panel all render correctly
with real API data. Not yet committed.

## In flight

Nothing blocking. Web UI redesign is done and verified; next action is committing it (see
"Next up").

## Known problems

**This machine's `Z:` drive (Windows) is an SSHFS mount of the same filesystem this project
lives on, and its Windows driver returns `EPERM` instead of the POSIX-standard `EEXIST` when
something calls `mkdir` on a directory that already exists.** Confirmed directly: a one-line
Node script calling `fs.promises.mkdir('.')` from the project root prints `EPERM` on `Z:` vs.
`EEXIST` for the identical call on a real local Windows drive. This breaks anything that does
an idempotent/defensive `mkdir` on an existing directory while working from `Z:` on Windows:
`npm install` (npm's Arborist does this before reifying, so a from-scratch install can't repair
a broken `node_modules` from that shell), and by extension `npm test`/`npm run lint`/`npm run
web` whenever they need something `npm install` would have fixed. It also affects Claude Code's
own file-write tooling on that path.

**Workaround that resolved it this session:** SSH directly into the host instead of going
through the Windows SSHFS mount (`ssh aviv@100.76.172.46`, key-based, then
`cd shared_disk/Cursor_apps/Eps_Evaluation`). Same filesystem, same files, but native Linux
`mkdir` semantics -- `npm install`/`test`/`lint`/`build`/`web` all work normally there. This is
now the reliable path for running anything in this project from that Windows machine, until/
unless the `Z:` mount itself gets remounted with different options. A stray empty file named
`mkdir` was left behind from an earlier failed diagnostic `npm install` attempt on `Z:` and has
been deleted.

## Next up

1. Commit the web UI redesign (`src/web/public/{index.html,app.js,style.css}` +
   `CURRENT_WORK.md`).
2. No other open implementation work beyond that.

## Log

- 2026-08-14 -- Bootstrapped repo with the CodeFundation starter kit.
- 2026-08-14 -- Planned (base app + average-P/E amendment), then implemented the full app
  (data layer, valuation layer, CLI, web) across tasks 1-9. 66/66 tests passing. Task 10
  (live end-to-end check) blocked on the API-key secrets file pending user action.
- 2026-08-15 -- API key configured; ran task 10 against the live API, found and fixed two
  plan-tier issues (`growth_estimates` 403, `income_statement` outputsize cap) plus a port
  collision. 67/67 tests passing. Expanded `CLAUDE.md` with Architecture/Gotchas. Committed
  everything (`7821413`).
- 2026-08-15 -- Redesigned web UI per user feedback (price banner with upside/downside vs.
  current price, growth-sources panel, valuation-multiples panel). Hit a Windows/SSHFS `mkdir`
  bug on the `Z:` mount that blocked `npm install`/`test`/`lint`/`run web` and the file-write
  tools; diagnosed the root cause, then resolved it for this session by connecting directly via
  SSH to the same host/filesystem instead of through the Windows mount. Ran the full suite
  (67/67 passing), lint, and build clean there, started the web server, and visually verified
  the redesign end-to-end (price banner, growth panel, multiples panel) against a live MSFT
  lookup through an SSH port forward. Ready to commit.
