# Project: Financial Charts

A Python tool that fetches a company's fundamentals (US and TASE markets) and renders a
fixed, Qualtrim-style grid of charts all at once, for investor evaluation.

## Commands

- Build: `uv sync`
- Test (all): `pytest -q`
- Test (single): `pytest -q path/to/test_file.py::test_name`
- Lint: `ruff check`
- Format: `ruff format`
- Run locally (CLI): `python -m financial_charts <TICKER> [--source --period --range --chart-set --charts --out]`
- Run locally (web UI): `python -m financial_charts.web --port 8000`
- Verify a source: `python -m financial_charts verify-source <name> --ticker <sample>`
- Inspect declared capabilities: `python -m financial_charts capabilities [<name>] [--matrix]`
- Regenerate a capability from live probes: `python -m financial_charts commission-source <name>`

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
  (e.g. `sources/yfinance/` holding the adapter's fetch, its mapping-to-template, its
  capability declaration, and tests together).
- Depend on published interfaces only — never reach into another module's internals.
- A change should touch one slice and its tests. If it can't, say so before implementing.

### 3. Surgical changes
- Touch only what the task requires. Clean up only your own mess.
- Don't refactor unbroken adjacent code or "improve" what you happened to read.
- Match the existing style, even where you'd have chosen differently.
- Only remove dead code that your own change created.

## Architecture

Data flows one way: **env-configured data source → per-source adapter → canonical template →
display**. The display layer reads only the template and never touches a data source directly.

- **Pluggable data sources, chosen by env config.** `yfinance` is the free tier; a paid-tier
  source must be swappable in without changing the display layer. Selection via an env var
  (e.g. `DATA_SOURCE`); API keys come from env, never committed.
- **One adapter ("converter") per source** — loads that source's endpoints and maps them
  onto the canonical template. Each source's differing endpoints/field names/availability are
  absorbed here; nothing downstream may know which source produced the data.
- **Canonical template = the single display data model,** implemented as Pydantic models
  (validated at the adapter boundary, serializes to JSON for caching/inspection). Every
  monetary series is a `Money`-style `(value, currency, scale)` value tagged with its currency
  and unit.
- **Source capability declaration + validation.** Capabilities are declared **config-as-code
  per source** (`sources/<name>/capability.py`: metrics, history depth — e.g. paid = 10y,
  free = 4y — markets/periods). Render-time `validation.py` turns the declaration into
  user-facing limits; a separate **explicit `verify-source` command** reconciles the
  declaration against a live API when a source is introduced/changed. **Renders never probe
  live** — they trust the declared capability, so "missing data" is a declared property, not a
  runtime surprise. See [SPEC.md](SPEC.md) for the onboarding flow.
- **Markets: US + TASE, native currency only** (₪ for TASE, $ for US; no FX conversion).
- **Caching:** adapters cache the template to disk (keyed by ticker + source + period + range +
  date); the display reads cache-first. Paid sources are metered — caching is a cost/reliability
  concern.

Suggested layout: `sources/<name>/` (adapter + capability declaration), `sources/validation/`
(capability/config validation), `template/` (Pydantic models + `Money` + missing-data/timeframe
rules), `cache/` (on-disk template cache), `charts/<name>/` (each reads the template),
`dashboard/` (grid assembly). Full design — chart inventory, per-source capability matrix,
tasks, edge cases — is in [SPEC.md](SPEC.md). Decided there: **static** CLI output (matplotlib +
HTML/PNG/PDF) — the browser dashboard in `web/` is interactive (Plotly.js) — paid source =
**Twelve Data** (free = yfinance), routing by **`.TA` suffix**, period/range **configurable per
render**.

## Verification policy

- Every change ends with its check passing: run `pytest -q` (or the relevant single test)
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

At the start of a session: read the git log and PROGRESS.md (if present) before making
changes. Complete one feature at a time. Leave the code mergeable — no half-done work
without a note in PROGRESS.md.

## Repository etiquette

- Branch naming: `feature/<slug>`, `fix/<slug>`
- Never commit API keys or fetched/cached financial data; data-source credentials live in
  `.env` (env-configured) and stay out of git; keep generated chart outputs out of git.

## Gotchas

- Build order and full detail live in [SPEC.md](SPEC.md) — implement it task by task in a
  fresh session. Sources: yfinance (free) + Twelve Data (paid). Output is static (no live
  toggles). Note: Twelve Data / yfinance TASE *fundamentals* coverage is uneven — the
  capability/validation module is what surfaces those gaps.
- Fundamental-data sources return sparse / `None` fields for some tickers and periods —
  normalize missing data and time frames at the adapter/template boundary so every chart can
  degrade to "No Data" gracefully.
- TASE unit trap: prices are in agorot (1/100 ₪) but financial reports are in millions of
  shekels. Never assume a single currency/unit per company — every template series is a
  `Money` value carrying its own currency + unit, and the adapter converts before storing.
- A source's limits (e.g. free tier = 4y history) are declared capabilities, not runtime
  surprises — validate a new source against the protocol and surface its limits to the user
  rather than rendering silent blanks.
