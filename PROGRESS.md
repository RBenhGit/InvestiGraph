# InvestiGraph merge — progress

Full plan: `docs/MERGE_SPEC.md`. Read this file before starting any merge-related work in a new
session; update it at the end of every phase (close-out checklist in `docs/MERGE_SPEC.md`).

- [x] **Phase 0 — Initialize the project.** `docs/MERGE_SPEC.md` and this file created;
      `CLAUDE.md` placeholders filled in; project memory saved; `valuation-porter`,
      `data-layer-porter`, `history-porter` agent definitions written to `.claude/agents/`.
- [x] **Phase 1 — Freeze and baseline the sources.** Financial_Charts' dirty working tree
      committed (`dd1ed4d`). Baselines recorded: Financial_Charts `uv run pytest -q` → 326
      passed; Eps_Evaluation `npm test` → 289 passed under Node 22.23.2 (installed via nvm,
      user-local, system default left at v18). `pre-investigraph-merge` tagged in
      Financial_Charts and pushed; tagged locally only in Eps_Evaluation (not pushed — its
      `origin` is `avivinvetsting/Eps_Evaluation`, not ours; pushing there would contradict the
      hard-fork decision).
- [x] **Phase 2 — Import both histories into InvestiGraph.** Done on branch
      `merge/import-sources` (not yet merged to `main` — this and Phase 3 stay on this branch
      per CLAUDE.md's "risky/multi-session work" rule; Phases 4–6's worktrees branch off its
      tip, not off `main`). 125 commits total. Both import commits verified as true 2-parent
      merges with the original history reachable via the second parent (e.g. Financial_Charts'
      `template/models.py` and Eps's `valuation/lynch/index.ts` both show their full original
      commit lists). Note: `git log --follow` does *not* show this directly — it can't detect
      a rename across differently-prefixed merge parents; that connects up once Phase 3's
      `git mv` creates an actual rename commit for `--follow` to walk through.
- [x] **Phase 3 — Make Financial_Charts the trunk.** Rename confirmed with the user (proceed).
      `src/financial_charts` → `src/investigraph`, `pyproject.toml` renamed, ~100 files'
      `financial_charts.` imports rewritten to `investigraph.` (326 tests still passing,
      unchanged from baseline). Hooks wired to real commands (`ruff format`/`check`, `pytest`)
      and smoke-tested. `SPEC.md`, `Project_ReEvaluation_2026-08-02.md`, and FC's `PROGRESS.md`
      (renamed `docs/financial_charts_progress.md` — kept separate from this file rather than
      merged, since they track different things: this file tracks merge phases, that one is
      FC's own historical task-completion log) moved to `docs/`. Three source `.gitignore`s
      merged into one root file. **Scope correction from the original plan:** Phase 9's step 5
      assumed `legacy/financial_charts/` would already be empty after this phase; it isn't —
      `.claude/` (hooks, agents, agent-memory, skills, settings.json), `README.md`, `CLAUDE.md`,
      `.env.example`, and `.gitignore` are deliberately left there, since reconciling them
      against InvestiGraph's own `.claude/` and root docs is explicitly Phase 9's job, not
      Phase 3's — moving them now would be scope creep into a later phase's decisions. Phase 9
      needs to account for this leftover, not assume an empty directory.
- [ ] **Phase 4 — Port the valuation domain.** IN PROGRESS — launched as a background
      `general-purpose` agent (isolated worktree, branched off `merge/import-sources` @
      `2835e70`), briefed with the full `valuation-porter` spec inline. (Note: the
      `.claude/agents/valuation-porter.md` etc. definitions written in Phase 0 were not picked
      up as registered subagent types this session — the harness's available-agent list didn't
      refresh — so all three porters below run as `general-purpose` with the brief embedded in
      the launch prompt instead of loaded from the agent file. Functionally equivalent; worth
      checking in a fresh session whether the named agents register correctly.)
- [ ] **Phase 5 — Extend the data layer.** IN PROGRESS — same setup, `data-layer-porter` spec.
- [ ] **Phase 6 — Port the history store.** IN PROGRESS — same setup, `history-porter` spec.
- [ ] **Phase 7 — Converge and build the merged web app.** Starts only after 4–6 merge to
      trunk and pass a combined `code-reviewer` pass.
- [ ] **Phase 8 — Front-end tests.** Wire vitest as a dev dependency; `scripts/test.sh` runs
      both suites, invoking Node 22 explicitly (see the resolved Node-version item below).
- [ ] **Phase 9 — Harness, docs, cleanup.** Merge `.claude/`, prune `CLAUDE.md`, retire the
      porter agents, remove `legacy/eps_evaluation/`.

## Open items carried from Phase 0

- **Node version — resolved.** Eps_Evaluation's README claimed vitest needs Node ≥20.12; the
  real constraint is ≥22 (`yahoo-finance2@4.0.2` and `whatwg-url@17.1.0` both declare
  `engines.node >= 22`, and the suite hard-fails on Node 20 with an unrelated-looking
  `undici`/webidl error until 22 is used). Node 22.23.2 is installed via nvm at
  `~/.nvm/versions/node/v22.23.2/bin` — nvm's default alias is set back to `system` so every
  other shell/project on this machine keeps seeing system Node v18.19.1 unchanged; Phase 8's
  `scripts/test.sh` needs to invoke this Node 22 binary explicitly (or document `nvm use 22`)
  rather than relying on `$PATH`.
- **Phase 3 rename (`financial_charts` → `investigraph`):** recommended but explicitly
  skippable; if skipped, all later paths referencing `src/investigraph/...` in
  `docs/MERGE_SPEC.md` and the agent definitions become `src/financial_charts/...` instead.
