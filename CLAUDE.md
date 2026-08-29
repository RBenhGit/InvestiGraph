# Project: InvestiGraph

## Commands

- Build: `uv sync`
- Test (all): `scripts/test.sh` (runs `uv run pytest -q` plus `npx vitest run` for the front-end tests; `uv run pytest -q` alone for a backend-only check)
- Test (single): `uv run pytest -q <path>::<test_name>`
- Lint: `uv run ruff check`
- Format: `uv run ruff format`
- Run locally: `uv run python -m investigraph.web --port 8000`

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
  (e.g. `valuation/lynch/`, `sources/yahoo_consensus/` holding handler, validation, and its
  tests together).
- Depend on published interfaces only — never reach into another module's internals.
- A change should touch one slice and its tests. If it can't, say so before implementing.

### 3. Surgical changes
- Touch only what the task requires. Clean up only your own mess.
- Don't refactor unbroken adjacent code or "improve" what you happened to read.
- Match the existing style, even where you'd have chosen differently.
- Only remove dead code that your own change created.

## Verification policy

- Every change ends with its check passing: run `uv run pytest -q` (or the relevant single test)
  and show the output. If you can't verify it, don't call it done.
- Fix root causes. Never suppress an error, skip a test, or weaken an assertion to get green.
- For bug fixes: write a failing test that reproduces the issue first, then fix it.

## Workflow

- Non-trivial changes (multi-file, unfamiliar code, uncertain approach): explore and plan
  first; skip planning for one-line fixes.
- For risky or multi-session work, start from a worktree on a new branch and confirm the
  suite is green BEFORE the first edit — then any later failure is attributable to this change.
- Before treating a feature as done, review the diff against the plan in a fresh context
  (code-reviewer agent or /code-review).
- Commit with a descriptive message after each completed unit of work.

## Multi-session projects

At the start of a session: read the git log and PROGRESS.md before making changes. Complete
one feature at a time. Leave the code mergeable — no half-done work without a note in
PROGRESS.md. `docs/MERGE_SPEC.md` records the plan and rationale behind InvestiGraph's origin
as a merge of Financial_Charts and Eps_Evaluation — read it when a design decision (the single
canonical template, the shared growth-fallback chain, `Money`'s currency/scale tagging) needs
its "why."

## Repository etiquette

- Branch naming: `<type>/<slug>` (e.g. `fix/history-race`, `feat/live-prices`) — short and
  descriptive. `merge/<slice-name>` was reserved for the now-complete Financial_Charts +
  Eps_Evaluation merge (Phases 4-9, worktrees under `../investigraph-<slice>/`); no need to
  reuse it for new work.
- This repo is a hard fork of `avivinvetsting/Eps_Evaluation` (via `RBenhGit/Financial_Charts`
  and `RBenhGit/Eps_Evaluation` clones) — no upstream sync is expected or attempted.

## Gotchas

- **TASE agorot trap:** TASE prices are quoted in agorot (1/100 ₪) while financial statements
  are reported in millions of shekels. Every `Money` value is tagged with `(currency, scale)`
  precisely so these can never be silently combined — see `template/models.py`'s `Money.to()`
  and `require_same_currency()`.
- **The growth-rate fallback chain must not drift between the CLI and the web UI.** It is one
  function (`analyst_estimate_5y → historical_3y → historical_1y → None`), called from both
  entry points — it has already drifted apart once in the pre-merge Eps_Evaluation codebase and
  produced different fair values for the same ticker from the two interfaces. Never default a
  missing growth rate to `0`; that fabricates a fair value instead of surfacing
  `MISSING_GROWTH_RATE`.
- **A NaN gap-marker must match its series' value type.** `template/derived.py` and
  `template/trailing.py` mark a bad/missing point as NaN (instead of omitting it) so a chart line
  visibly breaks at the gap rather than interpolating straight through it. Most series are
  plain-`float`-valued, where `float("nan")` is correct — but flow metrics (revenue, net_income,
  eps, fcf, ebitda, R&D, SG&A, dividends_paid, ebit) are `Money`-valued, and `MetricSeries`
  validation only checks consistency *among* the `Money` points, so a bare float slips through
  undetected and crashes every renderer at `.value.value`/`.value.as_base_units()` instead. Use
  `trailing.py`'s `_nan_like(value)` (returns a `Money`-tagged NaN when `value` is `Money`) any
  time this convention is applied to a new series — never construct the marker with a bare
  `float("nan")` literal without first checking the series' value type.
