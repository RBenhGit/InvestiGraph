# InvestiGraph merge — progress

Full plan: `docs/MERGE_SPEC.md`. Read this file before starting any merge-related work in a new
session; update it at the end of every phase (close-out checklist in `docs/MERGE_SPEC.md`).

- [x] **Phase 0 — Initialize the project.** `docs/MERGE_SPEC.md` and this file created;
      `CLAUDE.md` placeholders filled in; project memory saved; `valuation-porter`,
      `data-layer-porter`, `history-porter` agent definitions written to `.claude/agents/`.
- [ ] **Phase 1 — Freeze and baseline the sources.** Commit Financial_Charts' 8 dirty files,
      tag `pre-investigraph-merge` in both source repos, record each suite's green baseline
      (Eps_Evaluation's `npm test` needs Node ≥20.12 — local is 18.19.1, unresolved).
- [ ] **Phase 2 — Import both histories into InvestiGraph.** `git read-tree --prefix` both
      repos under `legacy/`.
- [ ] **Phase 3 — Make Financial_Charts the trunk.** Move `src/financial_charts` →
      `src/investigraph`, wire hooks for real, rewrite imports.
- [ ] **Phase 4 — Port the valuation domain.** Owner: `valuation-porter` agent, worktree
      `../investigraph-valuation`.
- [ ] **Phase 5 — Extend the data layer.** Owner: `data-layer-porter` agent, worktree
      `../investigraph-data`.
- [ ] **Phase 6 — Port the history store.** Owner: `history-porter` agent, worktree
      `../investigraph-history`.
- [ ] **Phase 7 — Converge and build the merged web app.** Starts only after 4–6 merge to
      trunk and pass a combined `code-reviewer` pass.
- [ ] **Phase 8 — Front-end tests.** Wire vitest as a dev dependency; `scripts/test.sh` runs
      both suites. Blocked on Phase 1's Node-version resolution.
- [ ] **Phase 9 — Harness, docs, cleanup.** Merge `.claude/`, prune `CLAUDE.md`, retire the
      porter agents, remove `legacy/eps_evaluation/`.

## Open items carried from Phase 0

- **Node version:** local Node is 18.19.1; Eps_Evaluation's vitest suite needs ≥20.12. Must be
  resolved in Phase 1 or Phase 8's plan changes (Playwright rewrite, or ship untested `app.js`).
- **Phase 3 rename (`financial_charts` → `investigraph`):** recommended but explicitly
  skippable; if skipped, all later paths referencing `src/investigraph/...` in
  `docs/MERGE_SPEC.md` and the agent definitions become `src/financial_charts/...` instead.
