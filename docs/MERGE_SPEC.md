# Merge spec: Financial_Charts + Eps_Evaluation → InvestiGraph

This is the durable, in-repo record of the InvestiGraph merge plan. The original plan was
authored interactively and lives (ephemerally) at
`~/.claude/plans/i-have-to-projects-luminous-elephant.md`; this file is what survives once that
conversation is gone. Read this and `PROGRESS.md` before touching merge work in any new session.

## Context

Two finished, independently-built stock analysis tools shared a subject (a ticker), a data
provider (Twelve Data + Yahoo), a caching problem, and a user — but nothing else. Looking at a
company meant running two apps, on two ports, in two languages, each with its own API key, its
own disk cache, and its own idea of what EPS is.

| | Financial_Charts | Eps_Evaluation |
|---|---|---|
| Path | `/home/rbh-home/Desktop/finance/stock_tools/Financial_Charts` | `/home/rbh-home/Desktop/finance/Eps_Evaluation` |
| Stack | Python 3.12 / uv / Flask / matplotlib / Plotly | Node / TypeScript / Fastify / vanilla JS / Chart.js |
| Size | ~9.9k LOC, 51 commits | ~10.0k LOC, 68 commits |
| Remote | `RBenhGit/Financial_Charts` (owned) | `avivinvetsting/Eps_Evaluation` (not owned) |
| Branch merged | `main`, 1 ahead of origin | `rbh_fix`, 1 ahead of `main` |
| Did | 21-chart fundamentals dashboard, US + TASE, CLI + web on :8000 | Lynch + Rule #1 fair value, Bear/Base/Bull, saved history, CLI + web on :3210 |

**Outcome:** one repo (`RBenhGit/InvestiGraph`), one Python runtime, one cache, one `.env`, one
server — one page where a ticker gets typed once and returns the chart grid *and* the
fair-value panel, with the P/E and EPS charts next to the valuation that uses them.

## Four decisions (locked before implementation started)

1. **Single Python app.** Financial_Charts' spine survives; Eps_Evaluation's logic is ported to
   Python and its front end moves over verbatim as static assets. Rationale: the TS code that
   must actually be *rewritten* is small (~130 LOC valuation math, ~325 LOC history store,
   ~230 LOC Yahoo adapter); the 2,700-LOC vanilla-JS front end is framework-free and moves
   unchanged. The reverse direction would mean rewriting Financial_Charts' Pydantic canonical
   model (`Money` currency/scale guards), the capability-declaration system, both source
   adapters, 21 matplotlib charts, and static PNG/PDF export that has no TS equivalent —
   ~6,000 LOC, discarding the better-structured half of the merge.
2. **One dashboard per ticker**, not two pages behind one nav bar — the payoff that justifies
   the merge.
3. **Preserve both git histories** via `git subtree`-style import (`git read-tree --prefix`) —
   all 119 commits and per-file blame survive under `legacy/financial_charts/` and
   `legacy/eps_evaluation/` before being moved to their final homes.
4. **Hard fork from Aviv's repo.** `rbh_fix` (one commit ahead of `avivinvetsting/main`) is the
   source of truth; no sync back to `avivinvetsting/Eps_Evaluation` is planned or attempted.

**The one honest wrinkle:** `web/public/app.test.js` (1,316 LOC) and `valuations.test.js`
(390 LOC) are jsdom tests over browser JS kept verbatim — Python cannot run them. Phase 8
resolves this (keep vitest as a dev-only dependency; `scripts/test.sh` runs both suites). It is
the only place "single Python app" needs a footnote.

## Starter-kit compliance

InvestiGraph is a CodeFundation project — this plan is held to its own `CLAUDE.md`:

- **Modularity** drives the whole shape: the port is organized as vertical slices
  (`valuation/`, `sources/yahoo_consensus/`, `history/`), each depending only on other slices'
  published interfaces (`sources/base.py`'s `Capability`, `template/models.py`'s
  `CompanyFundamentals`). This is also what makes Phases 4–6 safe to parallelize across agents.
- **Surgical changes** is flagged wherever a phase must touch more than its own slice: Phase 3's
  ~100-file import rewrite (mechanical, one commit, stated as skippable) and Phase 7's web-layer
  wiring (deliberately *not* parallelized — integration is the one place a change legitimately
  can't stay inside one slice).
- **Verification policy** — every phase ends with its own `pytest`/`vitest` check, shown in
  output, never skipped or weakened.
- **Workflow** — the merge runs from a branch with each source repo's own suite green before
  the first edit (Phase 1), per the "risky or multi-session work" rule.

**Every phase closes the same way:**
1. Its own test check (named per phase).
2. A `code-reviewer` pass over the diff against that phase's description, in a fresh context.
3. A commit with a descriptive message.
4. A one-line status update in `PROGRESS.md`.

## Phase list

| # | Phase | Owner |
|---|---|---|
| 0 | Initialize the project: docs, goals, memory, agent team | main session |
| 1 | Freeze and baseline the sources | main session |
| 2 | Import both histories into InvestiGraph | main session |
| 3 | Make Financial_Charts the trunk | main session |
| 4 | Port the valuation domain (pure functions) | `valuation-porter` agent |
| 5 | Extend the data layer (Yahoo consensus, EPS resolution, growth) | `data-layer-porter` agent |
| 6 | Port the history store | `history-porter` agent |
| 7 | Converge + build the merged web app | main session |
| 8 | Front-end tests: the one Node dependency | main session |
| 9 | Harness, docs, cleanup | main session |

Phases 4–6 run in parallel, each agent in its own git worktree/branch off the Phase 3 trunk,
merged back one at a time with the full suite run after each merge. Full detail — exact
commands, per-phase acceptance checks, each agent's knowledge base — lives in the plan file
referenced at the top of this document; re-derive it into this file if that plan file is ever
lost (e.g. via `git log`/PROGRESS.md history plus this summary).

## Verification (end-to-end acceptance)

On a clean clone with only `TWELVEDATA_API_KEY` set:

1. `uv run python -m investigraph.web --port 8000`, enter `AAPL` once → chart grid **and**
   Bear/Base/Bull fair-value cards render from a single fetch cycle.
2. Save a valuation with an evaluator name → appears on `/valuations.html` with a live price.
3. `uv run python -m investigraph valuate AAPL` → CLI fair value **matches the web UI's** for
   the same inputs (catches a drifted growth-fallback chain).
4. `uv run python -m investigraph TEVA.TA --source twelvedata --out out/TEVA.html` → TASE path
   still works, agorot handled correctly.
5. `ls .cache/` → one cache directory serving both features.

## Risk register

| Risk | Phase | Mitigation |
|---|---|---|
| Plan lives only in an ephemeral conversation/plan file | 0 | This file + `PROGRESS.md` + project memory make it durable and resumable cold |
| Financial_Charts' 8 dirty files lost in the import | 1 | Commit before Phase 2 — subtree imports commits, not working trees |
| Parallel agents collide on a shared file | 4–6 | File scopes barely overlap by design; merge back one at a time with full suite run after each; `code-reviewer` pass over combined diff before Phase 7 |
| yfinance can't supply some `AnalystConsensus` fields | 5b | Probe live and map fields before writing the adapter; missing → explicit `None` + documented gap |
| Front-end tests unrunnable (Node 18 vs ≥20.12) | 1 / 8 | Resolve in Phase 1; if unfixable, Phase 8's recommendation changes |
| Flask JSON shape drifts from Fastify's → `app.js` breaks silently | 7 | Port `server.test.ts` (791 LOC) as the contract before touching `app.js` |
| Growth fallback chain drifts between CLI and web | 5d / 7 | One shared function, tested from both entry points — has already happened once |
| Serial request handling feels slow vs. Fastify | 7 | Accept; `threaded=False` is a correctness requirement, revisit only with a measurement |
| Ticker charset narrows (no `AAPL:NASDAQ`) | 7 | Intentional; noted in the README |
