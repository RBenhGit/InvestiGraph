# Project Re-Evaluation — InvestiGraph

**Date:** 2026-08-29 (second pass, same day)
**Focus:** Full Project — targeted follow-up, not a full re-sweep
**Previous Reports:** 2026-08-02, Full Project — superseded by the 2026-08-29 report (removed).
2026-08-29, Full Project — **not superseded**, still the baseline this report extends. Everything
that report verified and marked "Match" is not re-derived here; this report only re-checks what
changed or was left open.

## Executive Summary

Nothing changed in the codebase's shape since the 2026-08-29 report — no new modules, no route
changes, no dependency changes. Two things happened in the same session, after that report was
written: (1) a Money-typed NaN gap-marker crash bug was found by a deep integration audit and
fixed in `template/trailing.py`, with corrected `yfinance`/`twelvedata` `capability.py`
history-depth numbers landing in the same commit; (2) the `merge/import-sources` branch (157
commits) was fast-forward merged into `main` and then deleted, both locally and on `origin`.

The **headline finding** is new and self-inflicted: `PROGRESS.md`'s "## Merge complete" section
(lines 280-286) now makes a **false current-state claim**. It says `main` "still points at the
pre-merge Financial_Charts tip" and "has not yet been merged" — both wrong as of this session's
later work. `main`@`8a64e98` has the Phase 9 tip (`198d034`) as an ancestor (fast-forward, verified
via `git merge-base --is-ancestor`), and `merge/import-sources` no longer exists on `origin`
(`git ls-remote --heads origin` returns nothing for it). This is the kind of drift the project's
own audit practice exists to catch, and it's fresh — introduced by this session's own later
actions, not carried over from before.

Everything else is either resolved or unchanged. The previous report's one open Section-1 mismatch
(test count, 500 documented vs. 503 actual) is now **resolved**: `PROGRESS.md`'s newest entry
records "507 pytest passing" (PROGRESS.md:355), which matches a live `pytest --collect-only -q`
run exactly. The previous report's Priority-3 recommendation — add a Post-merge features entry
for the then-uncommitted NaN-marking fix — is **satisfied**, at PROGRESS.md:318-355. The two new
doc passages added this session (CLAUDE.md's NaN-marker Gotcha, README's TTM gap-breaking
sentence) are both accurate against the code. The previous report's Section 2 gaps — three
undocumented Flask routes, undocumented `valuate` CLI flags, undocumented Rule #1 CLI defaults —
are **all still open, unchanged**, at the same line numbers.

---

## Findings

### 1. Documentation Accuracy — updates since the 2026-08-29 report

| # | Doc claim | Doc location | Code reality | Code location | Status |
|---|---|---|---|---|---|
| 1.1 | Test count: previously "500 pytest" (stale) vs. 503 actual, flagged Mismatch | [PROGRESS.md:316](../PROGRESS.md#L316) (historical, Phase 9's own point-in-time record — not restated as current) | Newest entry records "507 pytest passing"; live `uv run pytest --collect-only -q` → **507 tests collected** | [PROGRESS.md:355](../PROGRESS.md#L355) | **Resolved** — doc and code agree at 507, no drift |
| 1.11 (new) | NaN gap-marker must match its series' value type; use `_nan_like()` for `Money`-valued series | [CLAUDE.md:85-92](../CLAUDE.md#L85-L92) | `_nan_like(value)` defined exactly as described, both call sites gated by `mark_gaps=True` | [trailing.py:38](../src/investigraph/template/trailing.py#L38) (def), [trailing.py:90, 98](../src/investigraph/template/trailing.py#L90) (call sites) | Match |
| 1.12 (new) | A TTM window missing a quarter breaks the plotted line rather than interpolating across it | [README.md:74-76](../README.md#L74) | `derive_ttm_fundamentals` calls `ttm_series(..., mark_gaps=True)` for every flow metric, which appends a NaN-marked point at a gap instead of skipping it | [trailing.py:174](../src/investigraph/template/trailing.py#L174) (the call), [trailing.py:88-98](../src/investigraph/template/trailing.py#L88) (the NaN-append logic) | Match |
| 1.13 (new) | "`main` still points at the pre-merge Financial_Charts tip... has not yet been merged into it" | [PROGRESS.md:282-283](../PROGRESS.md#L282-L283) | `main`@`8a64e98` has Phase 9 tip `198d034` as an ancestor (fast-forward merge completed); `merge/import-sources` deleted both locally and on `origin` | `git merge-base --is-ancestor 198d034 HEAD` → true; `git ls-remote --heads origin` → no `merge/import-sources` ref | **Mismatch** — false current-state claim, see Recommendation P1 |

Rows 1.2–1.10 from the 2026-08-29 report were spot-checked and remain **Match**, unchanged code
paths (growth-fallback chain, `Money` guards, chart-set counts, valuation panel's forced
`Period.ANNUAL`, ticker regex, `/static/valuations.html`, env vars, TTM derivation, historical-docs
framing) — not re-tabulated here to avoid duplicating a still-valid table.

### 2. Undocumented Code — unchanged from the 2026-08-29 report

All six items the previous report flagged remain **open at the same line numbers**; README.md's
endpoint list ([README.md:48](../README.md#L48)) is unchanged since that report:

| # | Item | Code location | Doc coverage | Status |
|---|---|---|---|---|
| 2.1 | `GET /` (main picker page) | [app.py:162](../src/investigraph/web/app.py#L162) | Absent from README's endpoint list | **Still-open** |
| 2.2 | `GET /render` (server-rendered HTML dashboard, no front-end caller) | [app.py:200](../src/investigraph/web/app.py#L200) | Absent from README | **Still-open** |
| 2.3 | `POST /chart-sets` (save a custom chart set) | [app.py:226](../src/investigraph/web/app.py#L226) | Absent from README | **Still-open** |
| 2.4 | `valuate` CLI flags: `-s/--save`, `-m/--mos`, `-n/--notes`, `-H/--history` | [__main__.py:411-437](../src/investigraph/__main__.py#L411-L437) | README's `valuate` example shows only bare `valuate AAPL` ([README.md:82-85](../README.md#L82-L85)) | **Still-open** |
| 2.5 | Rule #1 CLI defaults: exit P/E 15, required return 15%, 10 years (`_CLI_EXIT_PE_MULTIPLE`/`_CLI_REQUIRED_RETURN_PERCENT`/`_CLI_YEARS`) | [__main__.py:399-401](../src/investigraph/__main__.py#L399-L401) | Not stated anywhere a user would see before running `valuate` | **Still-open** |
| 2.6 | `web/history_service.py`, `web/valuate_service.py` — no colocated test file | unchanged | Exercised indirectly via route/CLI tests (same assessment as before) | **Still-open (low risk)** |

### 3. Stale Branch/Status References (new section)

Grep for `merge/import-sources` and "not yet (been) merged" across every `.md` file in the repo
root and `docs/`:

| # | File:line | Text | Status |
|---|---|---|---|
| 3.1 | [PROGRESS.md:17](../PROGRESS.md#L17) | "...Done on branch `merge/import-sources` (not yet merged to `main`..." | Stale, but inside a Phase 2 historical entry describing state *as of Phase 2* — acceptable as a point-in-time record, same pattern as the old 1.1 test-count entry. Low priority. |
| 3.2 | [PROGRESS.md:147](../PROGRESS.md#L147) | "...see `git log` on `merge/import-sources` between the convergence-review commit and this one..." | Stale, and an **actionable instruction** referencing a branch name that no longer resolves (`git log merge/import-sources` now fails without the branch; would need the SHA or reflog instead). More likely to trip someone up than 3.1's narrative statement. Medium priority. |
| 3.3 | [PROGRESS.md:280-286](../PROGRESS.md#L280-L286) | "## Merge complete" section: "`main` still points at the pre-merge Financial_Charts tip... has not yet been merged into it." | **Stale and false as a current-state claim** — not a historical log entry, phrased as present-tense fact. Directly contradicted by the completed fast-forward merge and branch deletion. **High priority — this report's headline finding.** |

For contrast, [CLAUDE.md:64-67](../CLAUDE.md#L64-L67) already handles this correctly: "`merge/
<slice-name>` was reserved for the **now-complete** Financial_Charts + Eps_Evaluation merge...no
need to reuse it for new work" — past tense, no false claim. `README.md` and `docs/MERGE_SPEC.md`
have no `merge/import-sources` mentions at all (clean). The project can clearly keep this current;
`PROGRESS.md`'s "## Merge complete" section is simply the one place that was written before the
merge happened and never revisited after.

### 6. Test Coverage — refresh

**507 pytest tests collected** (live `uv run pytest --collect-only -q`, confirmed this pass),
matching `PROGRESS.md`:355's own recorded figure exactly — no drift. **105 vitest tests** across 2
files, unchanged from the 2026-08-29 report (no front-end files have been modified since; not
re-run this pass since nothing under `src/investigraph/web/static/` changed).

---

## Comparison with Previous Report (2026-08-29, same day)

| Prior finding | Current status |
|---|---|
| 1.1 (test count: 500 documented vs. 503 actual, "one commit behind") | **Resolved** — now 507 everywhere, doc and live count agree exactly. |
| 2.1–2.6 (three undocumented Flask routes, undocumented `valuate` flags, undocumented Rule #1 defaults, two untested service modules) | **Still open, unchanged** — verified at current line numbers above; none of this session's work touched README's endpoint/CLI documentation. |
| Priority 3 recommendation ("once the NaN-marking fix is committed, add its own Post-merge features entry") | **Satisfied** — [PROGRESS.md:318-355](../PROGRESS.md#L318-L355), a complete, accurately-scoped entry documenting both the fix and the capability-depth corrections, with the correct final test count. |
| (not a prior finding — newly introduced) | **New regression**: PROGRESS.md's "## Merge complete" section is now stale, having been overtaken by this session's own later merge-and-cleanup work. This is the one genuinely new item this pass surfaces. |

---

## Recommendations

### Priority 1 — Fix the stale "Merge complete" section (new, highest priority)

**[PROGRESS.md:280-286](../PROGRESS.md#L280-L286)** — replace the current text:

> All 9 phases done. `main` still points at the pre-merge Financial_Charts tip — `merge/
> import-sources` has not yet been merged into it. Merging this branch into `main` (and deciding
> whether to keep or squash the 125+ imported-history commits from Phase 2) is a deliberate
> next step for the user to trigger, not assumed here.

with something reflecting the completed state, e.g.:

> All 9 phases done. `merge/import-sources` was fast-forward merged into `main` on 2026-08-29
> (no divergence to reconcile — `main` was a strict ancestor), then deleted both locally and on
> `origin`; all 157 commits, including the 125+ imported-history commits from Phase 2, are
> preserved intact on `main`.

### Priority 2 — README.md documentation gaps (carried forward, unchanged, still valid)

Identical to the 2026-08-29 report's Priority 1 — not yet acted on:
1. Document `GET /`, `GET /render`, and `POST /chart-sets` in README's endpoint list.
2. Document the `valuate` CLI's `--save`/`--mos`/`--notes`/`--history` flags with an example.
3. State the Rule #1 CLI defaults (exit P/E 15, 15% required return, 10-year horizon) so a user
   isn't surprised by unconfigurable output.

### Priority 3 — Stale `merge/import-sources` narrative mentions (carried forward from §3 above)

Lower urgency than Priority 1 since these are inside historical Phase-log entries, not
current-state claims — but PROGRESS.md:147's instruction to `git log` the now-deleted branch name
will fail if followed, so it's worth a one-line fix (point at the SHA or note the branch was
deleted) next time that section is touched.

### Priority 4 — Everything else from the 2026-08-29 report

Unchanged since that report; not re-derived here. See that report's Priority 2 (no CLAUDE.md
changes needed), Priority 4 (no undocumented dependencies found), Priority 5 (no stale references
carried over from 2026-08-02), and Priority 6 (route-doc-lint test as a future coverage target) —
all still stand as written.
