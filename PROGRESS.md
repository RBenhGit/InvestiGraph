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
- [x] **Phase 7 — Converge and build the merged web app.** DONE, all 7 units, one reviewable
      commit per unit (see `git log 82ac565..HEAD` — the convergence-review fix commit onward —
      for the full trail; `merge/import-sources`, the branch this work originally lived on, was
      fast-forward merged into `main` and deleted after Phase 9). Turned out substantially larger
      than the original plan scoped — needed two ports the plan hadn't accounted for before the
      response could even be assembled.
      1. `valuation/historical_pe.py` (8 tests, ported 1:1 from `historicalPe.test.ts` —
         deliberately does *not* reuse `template/trailing.py`'s daily `PE_RATIO_TTM`, a
         different statistic that would silently change what "median 3y P/E" means) +
         `growth.py`'s `historical_5y_growth_percent` (display-only, not part of the fallback
         chain) + `resolve_eps.py`'s `ResolvedEps.template_eps_ttm` (the raw pre-Yahoo figure,
         needed separately from the resolved `eps_ttm`).
      2. `POST /api/valuate` (`web/valuate_service.py`) — incorporates the convergence review's
         Warning-2 fix (always fetches `Period.ANNUAL` for the valuation panel, independent of
         chart-grid period) as a design constraint from the start. **Bug found while writing the
         21 contract tests, fixed:** bear/bull `exitPeMultiple`/`requiredReturnPercent` used
         Python's `or` for defaulting, silently replacing an explicit `0` with the default (the
         original JS's `??` only substitutes for missing/null) — `bearExitPeMultiple: 0` must
         reach `calculate_rule_one_value` as `0`, not get rewritten to `10` first.
      3. `/api/history` (GET/POST), `/api/history/<id>` (DELETE), `/api/valuations` — new
         `web/case_conversion.py` (generic camelCase↔snake_case key converter, used at every
         request/response boundary since the Pydantic models have no field aliases) and
         `web/history_service.py` (incorporates the review's exception-mapping note: catches
         `(OSError, ValueError)` around every `history/store.py` call — `json.JSONDecodeError`
         is a `ValueError` subclass — not just the two typed exceptions).
      4. `/api/live-prices` (yfinance `fast_info["lastPrice"]` per ticker, one bad ticker never
         fails the batch; no original test existed to port, 5 written directly).
      5. CLI `valuate` subcommand (`__main__.py`) — calls the exact same
         `handle_valuate()`/`create_valuation()` the web routes use, so CLI/web parity holds by
         construction, not by discipline (the original kept two separate copies of this flow
         that drifted once).
      6. **Front-end unification.** `public/` moved to `web/static/` verbatim (Flask's default
         `static_folder` already resolves there, no config needed); `index.html` rewritten as
         one entry point where a shared `#ticker-input` drives both `/chart-data` and
         `/api/valuate` from one form submit (`app.js` needed zero edits — a 3-line glue script
         attaches its existing `handleSubmit` to the shared form). Three real collisions found
         and fixed between the two design systems' CSS (both defined `:root` custom properties
         named `--surface`/`--ink`/`--border` with different values; both defined a `.card`
         class with different meanings) — resolved entirely on the FC side (renamed to
         `--chart-*`, scoped under `#chart-section`), `style.css` stays verbatim as the plan
         required.
      Full suite: 490 passed. **Verified without a browser** (none available in this
      environment): live dev-server smoke test of all four key endpoints against real AAPL
      data, zero duplicate element ids across 69 in the rendered page, inline script/style
      blocks syntax- and brace-checked, every DOM id `app.js` looks up confirmed present in the
      merged markup. This is real signal, not a substitute for actually loading the page in a
      browser and clicking through it — flagging that gap explicitly rather than claiming full
      verification. **If a browser becomes available, the highest-value next check is simply
      opening `/`, entering a ticker, and confirming both halves render without visual
      surprises** — everything HTTP/JS-logic-verifiable already has been.
- [x] **Phase 8 — Front-end tests.** Done. Added root `package.json` (vitest ^4.1.10 + jsdom
      ^30.0.1 as dev-only dependencies, `engines.node >=22.22.2` — jsdom's own declared floor,
      not just "22") + `package-lock.json`, `vitest.config.ts` (`include:
      src/investigraph/web/static/**/*.test.js`), and `scripts/test.sh` (runs `uv run pytest -q`
      then `npx vitest run`). No test content changed — `app.test.js`/`valuations.test.js`
      (1,316 + 390 LOC) were already ported verbatim in Phase 7; this phase only made them
      runnable. Full suite: 490 pytest + 105 vitest, both green.
      `scripts/test.sh` resolves Node 22 explicitly rather than trusting `$PATH` (system default
      stays v18 per the Phase 0 nvm decision): prefers the nvm-installed
      `~/.nvm/versions/node/v22.23.2/bin` if present, else checks the active `node --version`
      against jsdom's real floor (22.22.2, via a `sort -V` comparison — not a regex that would
      wrongly accept the v22.0–v22.22.1 band) and fails loudly with an install hint if neither
      holds. Also bootstraps `npm install` automatically when `node_modules` is missing, so a
      fresh clone doesn't hit `ERR_MODULE_NOT_FOUND` after pytest has already run.
      **code-reviewer verdict: ready to commit**, no scope creep (`git diff bdabc3e HEAD --
      src/investigraph/web/static/` empty — only new files added). Two Warnings found and
      fixed before commit: the Node-version guard's regex accepted any v22.x though jsdom
      itself declares `^22.22.2`; and a fresh clone with no `node_modules` failed vitest with a
      confusing "Cannot find package 'vitest'" only after burning the pytest run first. Both
      verified post-fix (version-gate boundary tested at 22.14.0/22.22.1/22.22.2/23.0.0;
      fresh-clone bootstrap re-run end to end).
- [x] **Phase 9 — Harness, docs, cleanup.** Done — the merge's last phase. No application code
      touched (`src/`, tests, `scripts/` untouched — confirmed by both the diff and a green
      `scripts/test.sh`: 490 pytest + 105 vitest).
      **`.claude/` reconciliation.** Three separate setups existed (repo root; `legacy/
      financial_charts/.claude/`, a strict subset of root's; `legacy/eps_evaluation/.claude/`,
      which had 6 agents root lacked — `architecture-reviewer`, `codebase-cartographer`,
      `perf-investigator`, `security-auditor`, `task-implementer`, `test-auditor` — plus a
      `standards/` dir they depend on, 5 extra skills — `extend`, `harness`, `onboard`,
      `orient`, `slice` — and more robust hook implementations). User confirmed: bring the
      agents+standards in (root's existing `code-reviewer`/`test-writer`/`debugger` were
      byte-identical to eps_evaluation's, untouched); the 5 skills came along under the same
      call (generic, `disable-model-invocation: true`, no conflict). The 3 now-obsolete porter
      agents (`valuation-porter`/`data-layer-porter`/`history-porter` — Phases 4-6 they were
      built for are long merged) were deleted.
      **Hooks adapted, not copied verbatim.** `protect-files.sh` switched from substring
      matching (root's old version blocked `.env.example` as a false positive on `.env` —
      caught live, while writing this phase's own new `.env.example`) to basename matching
      with an allowlist, sourced from a new shared `protected-paths.sh`; new `protect-bash.sh`
      closes a real gap (root had no PreToolUse guard on `Bash`, so `echo x > .env` bypassed
      `protect-files.sh` entirely). `post-edit.sh` and `stop-test-gate.sh` picked up
      eps_evaluation's more defensive generic bodies (jq-presence checks, exit-127 detection,
      `stop-test-gate.sh`'s fingerprint-based skip-if-unchanged cache) but kept
      project-specific config: `post-edit.sh` stays `ruff format`/`ruff check`, `.py`-only (not
      eps's prettier/eslint — the front-end JS under `web/static/` is kept verbatim per
      MERGE_SPEC.md and isn't this project's to reformat); `stop-test-gate.sh`'s `TEST_CMD`
      points at `scripts/test.sh` (not eps's SSH-tunneled `npm test`, a workaround for an
      unrelated SSHFS bug on their own machine that doesn't apply here).
      **Agent memory merge.** `legacy/financial_charts/.claude/agent-memory/code-reviewer/`
      held 10 real findings from Financial_Charts' own review history, left there since Phase 3
      with a pointer memory explicitly flagging the merge as Phase 9's job. All 10 copied into
      root's collection (which already had 2 merge-era entries), the pointer file retired, one
      cross-reference repointed to the entry it actually meant, `MEMORY.md` rebuilt as one
      12-entry index. Nearly lost entirely: `git rm -r legacy/` was run before this was
      noticed — caught before committing, recovered via `git show HEAD:<path>` since nothing
      had been committed yet.
      **`legacy/` removed.** Both `legacy/eps_evaluation/` and `legacy/financial_charts/`
      deleted (git history keeps them reachable via the Phase 2 merge commits' second
      parents). Confirmed no code/config dependency on either — only docstring provenance
      comments (`ported from legacy/eps_evaluation/src/...`) remain, which is the intended
      citation style. Eps_Evaluation's own project-management artifacts (`CURRENT_WORK.md`,
      `wiki/`, `TASKS.md`, `PLAN_*.md`) were deliberately left behind, not ported.
      **Docs.** Root `README.md` — previously the generic, non-project-specific "Claude Code
      Starter Kit" template README, a real gap — rewritten from scratch (merged from
      Financial_Charts' old README + the app's actual current CLI/web surface). New root
      `.env.example` (didn't exist before), including `HISTORY_FILE_PATH`. `CLAUDE.md` lightly
      pruned: the Commands section's Test line simplified now Phase 8 is done, not upcoming;
      "Multi-session projects"/"Repository etiquette" reworded now the merge (and its
      `merge/<slice>` worktree branch convention) is closing — hard-fork note and the
      MERGE_SPEC.md pointer both kept.
      **code-reviewer verdict: needs fixes → fixed.** One Critical: `protect-bash.sh`'s
      write-boundary regex missed a redirect glued directly to a filename (`echo x >.env` /
      `>>.env` slipped through — only the spaced `> .env` form was actually blocked, contrary
      to what was believed verified). Fixed by adding `<`/`>` to the boundary character class;
      reverified against all three forms plus that reads (`cat .env.example`) still pass. Four
      Warnings in the newly authored docs, all fixed: `/valuations.html` doesn't exist (it's
      `/static/valuations.html`, Flask's default static path — verified with the test client);
      `commission-source`'s coverage caveat pointed at the wrong file (`PROGRESS.md` has no
      such caveat; it's in `docs/financial_charts_progress.md`); `--period ttm` documented
      without the "not yet supported by any source" caveat the original Financial_Charts README
      had; the narrowed ticker charset (no `AAPL:NASDAQ`) was never actually noted in a README
      despite `docs/MERGE_SPEC.md`'s risk register claiming it was — this was the first real
      README, so the last chance to close that stated mitigation.
      Full suite re-verified after all fixes: 490 pytest + 105 vitest, still green.

## Merge complete

All 9 phases done. `merge/import-sources` was fast-forward merged into `main` on 2026-08-29
(no divergence to reconcile — `main` was a strict ancestor), then deleted both locally and on
`origin`; all 157 commits, including the 125+ imported-history commits from Phase 2, are
preserved intact on `main`.

## Post-merge features

- [x] **2026-08-29 — Derive `Period.TTM` by summing trailing quarters.** `--period ttm` /
      `?period=ttm` previously failed pre-fetch ("source does not support period ttm") — no
      adapter declared it. Both `yfinance` and `twelvedata` adapters now derive it themselves:
      fetch `Period.QUARTERLY`, then sum each flow metric's trailing four quarters
      (`template/trailing.py`'s new `derive_ttm_fundamentals`, built on the pre-existing
      `ttm_series`/`derived.resolve` machinery — that machinery already existed for the three
      cherry-picked `PE_RATIO_TTM`/`DIVIDEND_YIELD_TTM`/`ROE_TTM` metrics; this applies the same
      classification codebase-wide). Balance-sheet metrics and `price` pass through their full
      quarterly series unchanged; `net_margin` is correctly recomputed from the TTM'd
      `net_income`/`revenue`; `gross_margin` passes through as a labeled approximation (its
      numerator isn't tracked as its own series in either adapter, so it can't be correctly
      recomputed) — **user's explicit choice** when asked "No Data" vs. approximate.
      Derivation lives inside each adapter's `fetch()`, not the CLI's or web's separate
      fetch-orchestration layers (they don't share one, unlike the valuation growth-fallback
      chain) — this avoids introducing a second CLI/web drift risk of the kind `CLAUDE.md`'s
      Gotchas section already warns about for that chain. Planned via `EnterPlanMode` (multi-file,
      real design decisions) before implementing.
      **code-reviewer verdict: no logic bugs** (independently verified the net_income/revenue
      TTM sums by hand against live yfinance and Twelve Data data), **5 doc/comment-accuracy
      Warnings, all fixed:** README/`docs/SPEC.md` claimed neither source returns a native TTM
      statement — false for yfinance (`ttm_income_stmt`/`ttm_cashflow` exist; the real reason to
      derive uniformly is cross-source consistency, not impossibility; folded into a new
      code-reviewer memory entry, `yfinance-has-native-ttm-statements.md`); "latest quarter"
      wording undersold that the *entire* quarterly series passes through unchanged, not just
      one point; a test comment claimed 5 quarterly points yield 1 TTM point (it's 2, now
      asserted); a CLI test name implied TTM is unsupported at the product level when it
      actually exercises the generic capability-gate mechanism via a deliberately limited stub
      (renamed). 500 pytest + 105 vitest passing.

- [x] **2026-08-29 — Deep integration & efficiency audit: NaN-gap-marker convention +
      capability-depth corrections.** Two pieces of uncommitted work landed together and were
      reviewed as one diff. (1) A shared "mark gaps as NaN instead of omitting them" convention
      across `template/derived.py`'s `resolve()`, `trailing.py`'s `resolve_trailing()`, and (new)
      `ttm_series()`, so a chart line visibly breaks at a bad/missing point instead of
      interpolating straight through it (previously-omitted points let a renderer draw a
      fabricated straight segment across the gap — see the code-reviewer memory entry
      `skipped-points-interpolate-across-gaps.md`). `ttm_series` gained a `mark_gaps: bool =
      False` keyword: default `False` preserves omit-semantics for `valuation/growth.py` and
      `valuation/resolve_eps.py`, which search by date among *present* points and would be
      corrupted by a NaN point; only `derive_ttm_fundamentals()` (the chart-rendering path) passes
      `mark_gaps=True`. (2) `sources/commission.py`'s history-depth probing was corrected to take
      the *max* depth across a sample's own metrics (excluding the new `RANGE_BOUNDED_METRICS`
      constant, moved to `sources/ranges.py`) rather than an effective min that let one naturally
      sparse metric understate a source's true depth, and to auto-declare `Period.TTM` at
      `Period.QUARTERLY`'s depth (TTM is derived, never fetched natively). Re-verifying against
      live data with the fixed probe corrected both sources' declared depths, which had never
      actually been checked: yfinance QUARTERLY 4y → **1y** (TTM likewise), Twelve Data ANNUAL
      10y → **6y**, QUARTERLY 10y → **1y**.
      **code-reviewer verdict (2 stages): one Critical bug, reproduced and fixed.** The first cut
      of the NaN marker used a bare `float("nan")` for every gap point, including in
      `ttm_series`'s flow-metric series (revenue, net_income, eps, fcf, ebitda, R&D, SG&A,
      dividends_paid, ebit) — all `Money`-valued, not float. A bare float mixed into an
      otherwise-`Money` series passed `MetricSeries` validation (which only checks consistency
      *among* the `Money` points) and crashed every renderer expecting `.value` to be `Money`
      uniformly (`AttributeError: 'float' object has no attribute 'value'` in
      `charts/base.py`'s `render_money_bar`/`render_money_line` and `web/chart_data.py`) —
      reproducible on any ticker with one missing quarterly cell viewed at `--period ttm`. Turned
      a silently-wrong chart into a hard 500 on the whole dashboard. Fixed with a new
      `_nan_like(value)` helper in `trailing.py` that tags the marker `Money(value=float("nan"),
      currency=..., scale=...)` when the series is `Money`-valued (`derived.resolve`'s own marker
      was never affected — every `DerivedMetric.compute` there returns a plain `float`).
      New regression test `test_derive_ttm_fundamentals_gap_point_renders_without_crashing`
      feeds a gapped `derive_ttm_fundamentals` output into the real `render_money_bar` — the
      producer→renderer seam no prior test covered, confirmed to fail against the pre-fix code
      and pass against the fix. Everything else in the diff (the `commission.py` probing-loop
      rewrite, the `RANGE_BOUNDED_METRICS` move, the corrected capability numbers) reviewed clean.
      507 pytest passing, ruff clean.

- [x] **2026-08-29 — Remove the Peter Lynch valuation method.** User request: drop Lynch
      entirely, leaving Rule #1 as the sole valuation method, with no dead code left behind.
      Deleted the `valuation/lynch/` slice and every consumer: the `lynch` key in
      `/api/valuate`'s response body, the CLI's "Method A" output line and history-table column,
      and the web UI's method card, price-delta, and history/valuations table columns.
      `lynch_fair_value` is gone from both `ScenarioValuation` and `SavedValuation` — **existing
      saved records still load**, because Pydantic's default `extra="ignore"` drops the
      now-unknown key rather than rejecting the record (verified against the real GOOG record in
      `data/evaluators/ran.json`, whose Rule #1 value and assumptions are unaffected); note the
      key is stripped permanently on that record's next write, which is intended here but
      one-way. Also removed what the deletion *made* dead rather than only what named Lynch:
      the `NEGATIVE_GROWTH_RATE` error code (Lynch-only — Rule #1 accepts a negative growth
      rate, since compounding a positive EPS never flips its sign), the `--accent-a-soft` CSS
      variable and the `.card.b`/`.card-eyebrow`/`.method-key-chip.a`/`.th-b` rules, and the
      now-meaningless "Method A"/"Method B" labelling in the CLI, the cards, and about.html's
      two-method prose. `docs/MERGE_SPEC.md`, this file's own earlier entries, and the dated
      re-evaluation reports deliberately keep their Lynch references — they are historical
      records of what was true when written, and rewriting them would falsify the record.
      **code-reviewer verdict (2 stages): no functional defects in surviving Rule #1 behavior;
      5 dead-code/stale-prose Warnings, all fixed** — three dangling doc references (index.html's
      "compare two ... estimates" lede, about.html's `see "Method B" above` cross-reference,
      two orphaned `.card-eyebrow` rules), one unreachable ternary arm in `renderScenarioColumn`
      (`prefix === 'rule-one' ? ... : ...`, whose false branch *was* the deleted light-background
      Lynch card), and one **pre-existing bug the removal surfaced**: the history table's Rule #1
      tint used `td.table-val:nth-of-type(4)`, but `renderHistoryTable` emits the Date/Evaluator/
      Price cells with `rowSpan` on a scenario group's first row only, so the Rule #1 cell sits
      at position 5 on the base row and 2 on the bear/bull rows — no single index can match both,
      and the tint had never worked on the main page. Confirmed empirically by probing the real
      rendered DOM (not by reading the selector), then fixed with an explicit
      `.table-val-rule-one` class set in both `app.js` and `valuations.js`, so the highlight lands
      correctly for the first time. Recorded as code-reviewer memory
      `nth-of-type-vs-class-column-highlight.md`. 498 pytest + 105 vitest passing, ruff clean.

- [x] **2026-09-13 — P/E average line, Twelve Data 429 retry, yfinance currency-mismatch
      messaging.** Three independent fixes bundled in one session:
      - **P/E ratio average line.** Both renderers (`charts/builtins/pe_ratio.py`'s matplotlib
        chart and `web/chart_data.py`'s `_pe_ratio` shaper, replacing the generic
        `_trailing_ratio_line` it used before) now draw a dashed gray horizontal line at the
        mean of the ticker's valid (non-NaN) TTM P/E points, labelled `Avg {x}x`. Needed a new
        `SeriesSpec.dash` field (plumbed through to Plotly's `line.dash` in
        `web/templates/index.html`) so the web chart's reference line reads as distinct from
        the real data line the way the matplotlib version's `linestyle="--"` already did —
        without it every series rendered solid and the average was visually indistinguishable
        from actual P/E history.
      - **Twelve Data 429 retry.** `TwelveDataAdapter._get` previously raised `SourceUnavailable`
        immediately on any `status: "error"` payload, including rate-limit (`code: 429`)
        responses — a burst of chart requests against the free tier's per-minute credit cap
        surfaced as a hard error rather than recovering once the window cleared. Now retries
        up to 3 times with a bounded backoff (2s/5s/10s) before giving up, since Twelve Data's
        docs specify no `Retry-After` header or fixed formula, only "implement retry logic for
        transient errors." Deliberately short and bounded rather than sleeping a full 60s,
        since the dev server is single-threaded (see `web/__main__.py`) and a per-minute window
        can clear well before a full minute if the request burst that exhausted it has stopped.
      - **yfinance unsupported financial-currency messaging.** A ticker whose financials are
        reported in a currency this app can't combine with its price currency (e.g. a
        foreign-domiciled filer like ASML reporting in EUR against a USD ADR) previously
        produced one generic "no data available" `source_limits` line per affected metric —
        revenue, EPS, P/E, dividend yield, etc. all separately, none naming the actual cause.
        `_fetch` now detects the unmapped `financial_currency` up front, strips those per-metric
        lines after they're generated (matched against the new
        `_FINANCIAL_STATEMENT_METRIC_IDS` tuple, kept in sync by hand with the
        `_statement_series` calls below it), and appends one line naming the real reason.
        `price`, keyed off `price_currency` separately, is unaffected.
      508 pytest + 105 vitest passing, ruff clean.

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
