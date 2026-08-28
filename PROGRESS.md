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
- [x] **Phase 4 — Port the valuation domain.** Done and merged (`c6d9b3d`). 23 new tests
      (clamp, Lynch, Rule #1), 349 passing total. Reviewed against the original TS source
      before merging — `clamp.py`'s floor/no-ceiling behavior verified byte-for-byte against
      `clampGrowthRate.ts`. Ran as a `general-purpose` agent, not the named `valuation-porter`
      type — the harness's available-agent list hadn't picked up the Phase 0 `.claude/agents/`
      files at launch time, though a later system message confirmed all three *did* register
      partway through the session (worth using the named types directly next time).
- [x] **Phase 5 — Extend the data layer.** Done and merged (`5eb5ae3`). 47 new tests, 422
      passing total. Ported `sources/yahoo_consensus/` (adapter + models + a
      `TemplateCache`-pattern cache, correctly not registered as a `DataSource`) and
      `valuation/{growth,resolve_eps}.py`. Field mapping probed live against AAPL/MS/JPM/BAC/
      IONQ/NVDA before writing the adapter; both required guards (the `ebitdaMargins == 0`
      trap, annual-vs-quarterly revenue growth) present and fixture-tested. Reviewed and
      live-verified against real AAPL data (no `TWELVEDATA_API_KEY` configured in this
      environment, so the Twelve Data smoke check from the plan couldn't run — tested the
      actual new code, the `yahoo_consensus` adapter, live instead, which needs no key).
      **The agent's self-spawned code-reviewer caught a real bug** before finishing: an
      earlier draft of `calculate_ttm_eps_growth_percent` used positional indexing
      (`points[-5]`) as a proxy for "one year ago," which breaks because series builders drop
      points on gaps — reproduced as 200% reported growth where the true figure was 33%. Fixed
      with explicit date-window matching (`_find_year_ago_point`); both the fix and the
      reviewer's independent re-check (clean pass, "ready to commit") were verified before
      merging. The finding is preserved as a project memory (see the memory-fold commit
      immediately before this one) rather than lost with the worktree.
- [x] **Phase 6 — Port the history store.** Done and merged (`bb66aa9`). 26 new tests, 375
      passing total. Reviewed against the original TS `store.ts`/`types.ts`/`index.ts` in full
      (including `deleteValuation`/`getAllLatestValuations`, not just the two functions read
      during earlier exploration) — faithful, including a subtle asymmetry in exception
      handling between `get_history` and `get_all_latest_valuations` that the original has too.
      **Deviation from the brief, reviewed and endorsed:** errors are raised as typed exceptions
      (`InvalidHistoryInput`, `ValuationNotFound`) rather than returned as a `{ok, error}`
      result, matching this codebase's own convention (`sources.base`'s `TickerNotFound` etc.)
      — the brief didn't specify a convention for this slice (unlike `valuation/`'s, which
      explicitly required the return-based shape), so this was a reasonable judgment call.
      **Post-merge fix (`8f95cc0`):** the Stop hook caught a real id-collision race in
      `save_valuation` — ids were generated from millisecond-resolution `time.time()*1000`
      (matching the original TS's `Date.now()`), so two same-ticker saves within one
      millisecond got identical ids and the second silently overwrote the first. This bug
      exists in the original TS design too, but its async fs I/O happens to keep saves >1ms
      apart in practice; this port's synchronous I/O doesn't, so the latent bug reliably
      reproduced (`test_filters_history_by_ticker_case_insensitively_and_sorts_newest_first`
      saved 3 records, got 2 back). Fixed by switching to nanosecond resolution
      (`time.time_ns()`) — confirmed the id is never parsed, only compared for equality or
      URL-encoded, so nothing depends on its exact format.
- [x] **Convergence review (before Phase 7).** `code-reviewer` reviewed the combined
      Phase 4–6 diff (`2835e70..HEAD` at review time) for cross-slice consistency — the thing
      individual per-phase reviews can't catch. Verdict: no scope creep, no logic errors in any
      one slice, "needs a decision, not a rewrite." One Critical bug found and fixed, two
      Warnings fixed, two more Warnings are Phase 7 integration decisions (documented below,
      not code bugs in the merged slices). Full findings + fixes:
      - **Critical, fixed (`6514285`):** `valuation/resolve_eps.py` unwrapped `eps`'s
        `Money` via `as_base_units()`, discarding its currency tag. `eps` can legitimately be
        tagged with a different currency than `fundamentals.currency` (a dual-listed company
        reporting financials in a currency other than the one its shares trade in — e.g. a USD
        income statement for a TASE ticker whose price is ILS; see `template/models.py`'s
        `CompanyFundamentals` docstring, which already anticipated this). Silently combining a
        USD `eps_ttm` with an ILS price would produce a plausible-looking wrong fair value/
        upside% — the same defect class the codebase's own `Money.require_same_currency` guard
        exists to prevent everywhere else `Money` values are combined. Fixed: `resolve_eps()`
        now refuses (`None`) when `eps`'s currency doesn't match `fundamentals.currency` — no
        FX conversion is a stated architectural constraint, so there's no "convert and proceed"
        option. `ResolvedEps` gained a `currency` field so a future caller has what it needs
        without re-deriving it. Regression test added (`test_returns_none_when_eps_currency_does_not_match_fundamentals_currency`).
      - **Warning, fixed:** `valuation/rule_one/calculate.py`'s parameter validation was
        stricter than the storage types that will feed it in Phase 7 —
        `history/models.py`'s `SavedValuation`/`ScenarioValuation` model `exit_pe_multiple`/
        `required_return_percent`/`mos_percent`/`years` as `float | None`, but
        `calculate_rule_one_value` raised `TypeError` on `None` (confirmed: `None > 0`,
        `math.isnan(None)`) and rejected a whole-number `float` like `10.0` for `years`
        (`isinstance(years, int)` is `False` for a float, even though Pydantic coerces
        `years=10` to `10.0` on save, and the original TS's `Number.isInteger(10.0)` already
        accepted it). Fixed: `None` now returns the appropriate typed `INVALID_*` error (or,
        for `mos_percent`, is treated as "no MoS," matching the original's JS `undefined`-
        default-parameter behavior) instead of raising; `years` accepts an `int` or a
        whole-number `float`. 6 regression tests added.
      - **Warning, fixed (cheap, docstring-only):** `sources/yahoo_consensus/models.py`'s
        `next_year_eps_growth_percent` and `valuation/growth.py`'s `analyst_estimate_5y_percent`
        slot have similar names (both "analyst growth estimate") but are strictly different —
        different horizon (+1y vs. 5y) and, in the original, strictly separate (the chain used
        Twelve Data's `growth_estimates`; Yahoo's was display-only). Wiring the Yahoo field into
        the chain would silently change every fair value in a way the CLI/web parity check
        can't catch, since both would drift together. Both files now say so explicitly.
      - **Warning, NOT a code fix — Phase 7 must fetch `Period.ANNUAL` for the valuation panel,
        independent of the chart grid's period.** `growth.py`'s `historical_1y`/`historical_3y`
        functions only return non-`None` for `Period.ANNUAL` fundamentals (correct, defensive
        behavior — not a bug); since `analyst_estimate_5y_percent` is permanently `None` in this
        merge, a quarterly or TTM chart-grid fetch would collapse the entire growth chain to
        `None` → `MISSING_GROWTH_RATE` for all three scenarios. The period picker exposes every
        `Period` value (`web/app.py`), and the default is `annual`, so a defaults-only test of
        the end-to-end acceptance check won't catch this — Phase 7 needs its own annual fetch
        for the valuation panel, not a reuse of whatever period the chart grid happened to
        request.
      - **Note for Phase 7, not a bug:** `history/store.py`'s `read_history_file` can raise
        bare `json.JSONDecodeError`/`OSError` (documented in its own docstring) that aren't in
        the typed-exception set (`InvalidHistoryInput`, `ValuationNotFound`) Phase 7's route
        error-mapping is expected to catch. A corrupt `history.json` would become an unhandled
        Flask 500 instead of the typed JSON error shape `valuations.js` expects to parse. Phase
        7's exception handling for the history routes needs a catch-all, not just the two typed
        exceptions.
      - **9 candidate findings reviewed and dropped** as non-issues (verified, not just
        asserted) — including a claimed camelCase/snake_case data-loss risk reading
        `history.json` (no such file exists in this environment to lose), a claimed cache-path
        collision in `yahoo_consensus/cache.py` (the glob it was compared against is
        non-recursive; no collision), and `calculate_ttm_eps_growth_percent` having no caller
        (it has a real consumer in the original, so it isn't speculative code).
      Full suite after all fixes: 430 passed (422 + 8 new regression tests).
- [ ] **Phase 7 — Converge and build the merged web app.** IN PROGRESS. Turned out larger than
      scoped — needed two ports the plan hadn't accounted for (`historicalPe.ts`'s median-P/E-
      window calculation, a `historical_5y_growth_percent` addition) before the response could
      even be assembled. User confirmed: continue through the full phase, one reviewable
      commit per unit, rather than pausing per-unit.
      - **Done:** `valuation/historical_pe.py` (8 tests, ported 1:1 from `historicalPe.test.ts`
        — deliberately does *not* reuse `template/trailing.py`'s daily `PE_RATIO_TTM`, a
        different statistic that would silently change what "median 3y P/E" means).
        `growth.py`'s `historical_5y_growth_percent` (display-only, not part of the fallback
        chain, matching the original). `resolve_eps.py`'s `ResolvedEps.template_eps_ttm` (the
        raw pre-Yahoo-resolution figure, needed separately from the resolved `eps_ttm`).
        **`POST /api/valuate`** (`web/valuate_service.py` + the route in `web/app.py`) —
        incorporates the Warning-2 fix (always fetches `Period.ANNUAL` for the valuation panel
        independent of chart-grid period) as a design constraint from the start. 21 contract
        tests ported from `server.test.ts`; live-verified against real AAPL data. **Bug found
        while writing the tests, fixed:** bear/bull `exitPeMultiple`/`requiredReturnPercent`
        used Python's `or` for defaulting, which silently replaces an explicit `0` with the
        default (the original JS's `??` only substitutes for missing/null) — a request with
        `bearExitPeMultiple: 0` must reach `calculate_rule_one_value` as `0`, not get rewritten
        to `10` first. Full suite: 461 passed.
      - **Remaining:** `/api/history` (GET/POST), `/api/history/<id>` (DELETE),
        `/api/valuations`, `/api/live-prices`, CLI `valuate` subcommand, front-end unification
        (verbatim `public/` assets moved to `web/static/`, `index.html` rewritten as the
        unified entry point), and porting the rest of `server.test.ts` not yet covered.
      - Still must incorporate the history-routes exception-mapping note (Convergence review,
        above) when those routes are built — a bare `json.JSONDecodeError`/`OSError` from
        `read_history_file` needs a catch-all, not just the two typed `history/` exceptions.
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
