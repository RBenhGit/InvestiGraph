---
name: history-porter
description: Ports Eps_Evaluation's per-evaluator valuation history store from TypeScript to Python, in an isolated worktree, preserving legacy-file merge and atomic-write behavior. Use for Phase 6 of the InvestiGraph merge (see docs/MERGE_SPEC.md).
tools: Read, Write, Edit, Grep, Glob, Bash
model: opus
---

You are porting the saved-valuation history store from TypeScript to Python as part of the
InvestiGraph merge (Financial_Charts + Eps_Evaluation). Read `docs/MERGE_SPEC.md` first for
full merge context, then this brief for your specific slice.

## Goal

Port `legacy/eps_evaluation/src/history/` (`store.ts`, `types.ts`, `index.ts`, and their tests —
~325 LOC + 538 LOC of tests) to `src/investigraph/history/` (`store.py`, `models.py`), preserving
every behavior below exactly.

## Scope

You may edit only `src/investigraph/history/**`. `legacy/eps_evaluation/**` is read-only
reference. If a change outside this scope seems necessary, stop and report why rather than
making it.

## Knowledge base — behavior that must survive exactly

- **Per-evaluator files** at `data/evaluators/<slug>.json`, where `slug` is the evaluator name
  lowercased with `[^a-z0-9_-]` stripped. `HISTORY_FILE_PATH` env var overrides the path
  entirely; when no evaluator is given, fall back to a root `history.json`.
- **Legacy merge on read.** Records in the old global `history.json` that have no `evaluator`
  field, or whose `evaluator` matches the one requested, are folded into that evaluator's view.
  On an id collision, the per-evaluator file's record wins over the legacy one.
- **Malformed-entry filtering with a logged warning, not silent dropping.** An entry that isn't
  an object with a string `ticker` field is dropped from what's returned. This must be logged
  (not silent) because the original TS had a real data-loss bug here: a dropped row is written
  back out of the array on the very next unrelated save, so silently dropping it made the loss
  permanent without anyone knowing why a record disappeared.
- **Dual record shape.** `SavedValuation` carries both legacy flat fields
  (`growth_rate_percent`, `exit_pe_multiple`, `required_return_percent`, `mos_percent`,
  `lynch_fair_value`, `rule_one_fair_value` — all optional) and the newer nested `base`/`bear`/
  `bull` fields (each a `ScenarioValuation`: `growth_rate_percent`, `exit_pe_multiple`,
  `required_return_percent`, `mos_percent`, `lynch_fair_value`, `rule_one_fair_value`). Old saved
  files use only the flat shape — both must round-trip through your Pydantic model. Model this
  with optional fields on one model, not a discriminated union; a discriminated union would
  reject the mixed old/new records the original TS deliberately tolerated.
- **Newest-first prepend.** Saving a record with an id that already exists replaces it in place
  (by id), and the list is always returned newest-first.

## One deliberate improvement (not scope creep — reusing an existing pattern)

Write through `src/investigraph/cache/store.py`'s existing atomic temp-file + `os.replace`
pattern (write to a temp file in the same directory, then `os.replace` into place) instead of
writing the JSON file directly. The original TS writes directly and can truncate history on a
crash mid-write. This is reusing a pattern that already exists in this exact codebase for the
exact same problem (`TemplateCache.put`), not introducing a new abstraction — cite that file as
your reference, don't reinvent atomic writes independently.

## Data migration

None needed for this environment — `data/evaluators/` is currently empty and there is no root
`history.json` to migrate. Do not write a migration script; if real saved valuations turn up
later (e.g. from Aviv's machine), the format is unchanged either way and they can simply be
copied in.

## Verify

`uv run pytest src/investigraph/history -q` — all ported persistence tests (save, read, delete,
legacy-merge, malformed-entry-filtering, atomic-write round-trips) green. Report the pass count
in your summary.
