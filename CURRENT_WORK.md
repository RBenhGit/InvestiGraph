# Current Work — Eps_Evaluation

**Updated:** 2026-08-25

## Where things stand

EPS×multiple stock valuation tool — Node.js + TypeScript, shared core (`src/data/`,
`src/valuation/`) with thin CLI (`src/cli/`) and web (`src/web/`) adapters.
**Cache-first optimization added:** `fetchStockData` and `fetchAnalystConsensus` now check local cache (24h TTL) before making external API calls, avoiding rate-limit hits when re-valuating or modifying assumptions. A "Refresh Live" button was added for explicit live market data refreshes.

## Last completed

- **Cache-first Data Layer:** Wired `getCachedStockData` and `getCachedYahooData` into the entry points with TTL checks and `forceRefresh` support.
- **Web UI & Server:** Added `forceRefresh` parameter to `POST /api/valuate` and a dedicated `🔄 Refresh Live` button in `index.html` + `app.js`. Re-calculating with different assumptions now runs in 0ms without hitting Twelve Data API rate limits.

Implemented the whole app in one pass (tasks 1-9), then several follow-ups:

- **Data layer** (`src/data/twelvedata/`): `fetchStockData(ticker)` — the single published
  entry point. Pulls quote, statistics, growth_estimates, quarterly/annual income statements,
  and monthly time series from Twelve Data; normalizes with guards against falsy-zero EPS,
  empty-but-200 responses, and currency mismatches. Includes average P/E over trailing
  1y/3y/5y (`historicalPe`), computed locally since the provider has no such field.
- **Valuation layer** (`src/valuation/`): pure functions, `calculateLynchValue` (PEG-style, no
  discounting) and `calculateRuleOneValue` (EPS projection x exit multiple, discounted once —
  still not DCF). Growth rate clamped to [-5%, 25%] before use in both.
- **CLI** (`src/cli/index.ts` + `formatOutput.ts`): `npm run cli -- TICKER`.
- **Web** (`src/web/server.ts` + `public/`): `npm run web` (Fastify, `PORT` default 3210).
- Wired `CLAUDE.md`'s Commands section and the `post-edit.sh`/`stop-test-gate.sh` hooks to the
  real npm scripts.

Committed as `c1ee656` (base app) and `7821413` (live plan-tier fixes: `growth_estimates` 403
on non-Enterprise keys degrades to null instead of failing; `income_statement?period=quarterly`
outputsize capped at 4; web server port 3000 → 3210; binds `0.0.0.0`).

**Web UI redesign** (`b889721`) — reorganized `src/web/public/{index.html,app.js,style.css}`
per user feedback (a flat, hard-to-scan stat strip). No backend/data changes. Added a **price
banner** (current price + both fair values as % upside/downside), a **growth-rate sources
panel** (all four growth figures side by side, active one highlighted), and a **valuation
multiples panel** (historical avg P/E 1y/3y/5y + trailing P/E + PEG, reference-only).

**Analyst-consensus feature** (`4a2bd07`) — the growth-sources and multiples panels above still
showed `n/a` for historical-5y growth, analyst-estimate-5y growth, and all three avg-P/E
figures at the time. Investigated: confirmed live against Twelve Data's own `api_usage`
endpoint that the API key is `plan_category: "pro"`, and its own error messages state
`growth_estimates` needs Ultra/Enterprise and full `income_statement` history needs Enterprise.
Added a second, independent data source rather than upgrading the paid plan or using an LLM
guess: `src/data/yahoo/` (sibling module, same shape as `twelvedata/`) wraps the
`yahoo-finance2` npm package's `quoteSummary` endpoint and exposes
`fetchAnalystConsensus(ticker)` — next-year consensus EPS growth, analyst price targets
(mean/high/low + count), and the consensus recommendation. Fully independent of `twelvedata/`;
`src/web/server.ts` fetches both in parallel, degrading `analystConsensus` to `null` (never
failing the whole request) if the Yahoo call fails. Added a third "Analyst consensus" panel.
75/75 tests, lint, build clean.

**Historical-5Y-growth / Avg-P/E data fix** (`4d54b50`) — the growth-sources and multiples
panels still showed `n/a` for `Historical, 5Y` and all three `Avg. P/E` figures even with the
Yahoo analyst-consensus panel added, because those specific figures were never routed through
Yahoo — they still depended on Twelve Data fields gated behind its plan tier. Confirmed live
that the real ceiling is `income_statement?period=quarterly` capping at 6 quarters (not 4 as
previously assumed) — an unfixable hard limit for a quarterly-TTM P/E scheme, since even the
max allowed (6) falls short of the 7 quarters `avg1y` needs. Ported the sibling `EvalApp`
project's approach (`D:\Investment Codes\EvalApp`): `historicalPe.ts` now computes one P/E
point per **fiscal year** (annual EPS + nearest-preceding monthly close — not subject to the
quarterly cap) and takes the **median** (not mean) over 1y/3y/5y windows, requiring only
`ceil(N/2)` valid points rather than an all-or-nothing full window — matches EvalApp's
`calcMedian` exactly, since with as few as 1-5 points per window a mean is too sensitive to one
outlier year. `historical5yPercent` now prefers `growth_estimates.past_5_years_pa` when
reachable, falling back to a locally-computed 5-annual-period CAGR (same shape as the existing
1y/3y CAGR) otherwise — no longer permanently `null` on this plan tier.
`fetchAnnualIncomeStatement`'s `outputsize` bumped 5→6 (confirmed live as the max this plan
allows) to have enough annual points for both the 5y CAGR and the 5-point P/E window.
`QuarterlyEpsPoint` type removed (dead after the switch to annual). 77/77 tests (was 75, +2
net new after also fixing one incorrect pre-existing test expectation), lint/build clean,
live-verified against AAPL: Historical 5Y 9.21%, Avg P/E 1Y/3Y/5Y 34.13/34.13/27.93 (previously
all `n/a`).

**Panel redesign** (`2d116c7`) — user feedback: the three reference panels felt dense/cramped
with equal visual weight, competing with the price banner and method cards. Growth-sources
panel now gets a pink (accent-a) top border (`panel-primary`, since it's the one panel whose
values actually feed the two valuation methods); the other two get a quiet neutral top border
and slightly reduced opacity (`panel-reference`). Each growth-source row gets a horizontal
bar-fill sized to `|value|` relative to the largest of the four sources, so "which source is
biggest" reads as a shape. More row padding, values now the dominant visual weight, labels
recede. Verified live in both light/dark and desktop/mobile (panel-primary border color,
bar-fill widths, responsive grid collapse, dark-mode `color-mix()` resolution all confirmed via
computed-style inspection).

**Documentation-drift fixes** — completed tasks 1-5 of `TASKS.md`. Fixed documentation drift in `CLAUDE.md` (added `yahoo` module, fixed `historicalPe` description), added `PORT` to `.env.example`, reworded the `outputsize=4` comment in `client.ts` to clarify it is deliberate, clarified the dead branch in `resolveTtmEps` docstring, and added cross-reference notes for the duplicated growth fallback chain. No behavioral changes made.
**Task 6 (CLI/Web divergence)** — updated `CLAUDE.md` to document that the CLI does not use the Yahoo analyst data (Option A chosen by user).

## In flight

Nothing in flight. Web UI got a full editorial redesign (`feature/mature-editorial-redesign`
branch) plus a 3-scenario (Bear/Base/Bull) side-by-side feature; the 3-scenario feature had a
real correctness bug (bear/bull's exit-P/E, required-return, and MoS were hardcoded and ignored
user input) and a broken build/4 failing tests, both fixed and verified live — see Log below.
Suite is 127/127 green, lint clean, build clean.

## Known problems

**Bugs found in the 2026-08-23 audits — all FIXED.** Earlier pass (API-boundary): the
`POST /api/valuate` 500s on malformed input, and the `renderPriceDelta`/`priceTargetValue`
zero-price divisions. Line-by-line pass added three more:

1. **`calculateCagrPercent` returned `NaN` for a swing to a loss** (`normalize.ts`). `epsPast`
   was guarded but `epsLatest` was not, so a negative ratio made `Math.pow(negative, 1/years)`
   return `NaN` for any `years > 1`. That `NaN` then reached `StockData.growth`, where BOTH
   adapters treat "not null" as usable — the CLI's `!== null` chain and the server's `??` chain
   would each select the `NaN` and **shadow a perfectly valid 1y CAGR below it**, so the
   valuation returned `MISSING_GROWTH_RATE` for a stock that had real growth data. Now returns
   `null` (plus a `years > 0` guard against an `Infinity` exponent). This one was invisible over
   HTTP because `JSON.stringify` turns `NaN` into `null` — it only bit the selection logic.
2. **Path traversal in the cache layer** (`cache.ts`). `ticker` was interpolated straight into
   `path.join`, so `X/../../PWNED` resolved _above_ the cache directory. `getCachedStockData`
   runs _before_ any network call in `fetchStockData`, so a caller-supplied ticker reached that
   read path on every lookup. Added `safeTickerSegment` (`^[A-Z0-9.:-]{1,20}$`, no `..`) at all
   four call sites; real punctuated tickers like `BRK.B` still work.
3. **`priceToSales !== undefined`** (`app.js`) — the _exact_ trap CLAUDE.md documents for the
   Financial Health header, surviving in a second spot. The field is `number | null` and never
   `undefined`, so the check was always true and rendered a permanent "P/S ratio (TTM): n/a"
   row for every ticker Yahoo has no P/S coverage for.

4. **HTML injection via `recommendationKey`** (`app.js`) — the most serious bug found all day,
   and found only on a _third_ pass over a file already audited twice. `tableRow` assigned its
   `value` straight to `innerHTML`, and one caller passes `recommendationKey`, a string that
   arrives verbatim from the Yahoo API. Verified in jsdom, not theorised: a payload of
   `<img src=x onerror=BOOM>` produced a real `<img>` element carrying a live `onerror`
   attribute. `tableRow` now renders text by default; the three locally-built `health-badge`
   spans (whose only interpolated parts are numbers via `fmt()`) opt in with `{ html: true }`.
   `notes` and `ticker` were already safe — they use `textContent`.

5. **Stale-response race in `handleSubmit`** (`app.js`) — the Go button was disabled during a
   request but **"Refresh Live" was not**, and nothing sequenced responses, so the LAST response
   to land won the DOM even when it belonged to an EARLIER request. Reproduced in a test: start
   an AAPL lookup, start an MSFT lookup before it returns, let AAPL resolve last — the page
   showed MSFT's banner with AAPL's data and `currentValuation.ticker` reverted to AAPL, so a
   Save would have persisted the wrong pairing. Fixed with a monotonic `latestValuateRequestId`
   (a superseded response returns before touching the DOM or the loading state), and
   `setLoading` now disables the Refresh button alongside Go.
6. **A `null` entry in `history.json` broke the entire history** — `readHistoryFile` checked
   `Array.isArray` but never the elements, so one stray `null` from a hand-edit threw on the
   first property access in BOTH `getHistory`'s ticker filter and the web UI's table render
   (losing every row, not just the bad one). `readHistoryFile` now drops entries that aren't
   objects with a string `ticker`.

7. **Lynch returned a NEGATIVE DOLLAR fair value for any shrinking company** — found only by
   running both methods over the 26 real cached tickers rather than by reading code. ABBV has a
   genuine -29.03% 3y EPS CAGR (clamped to -5%), and `EPS x growth%` then gave **-17.69 with
   `ok: true`**: the CLI printed "Method A (Lynch) fair value: -17.69" and the web banner showed
   a -108.85% "downside", both as if legitimate. The Lynch/PEG heuristic is only defined for a
   growing company, so this is now `NEGATIVE_GROWTH_RATE`. Rule #1 is unaffected (compounding a
   positive EPS at a negative rate shrinks it without flipping the sign — ABBV still yields a
   sane 7.86). **Consequence recorded in CLAUDE.md: the two methods no longer share a guard
   set**, so `lynch.ok` does not imply `ruleOne.ok`; the bear/bull fallback comment in `app.js`
   that asserted they fail together was corrected in the same commit.

**Audited and found sound:** `lynch`/`ruleOne` guards (`!(x > 0)` correctly rejects `NaN`),
`clampGrowthRate`, `resolveTtmEps`, `parseNumber`, the history endpoints (all malformed-input
cases return typed 400/404, verified by probe), and `saveValuation`/`deleteValuation` validation.
Also on the later pass: `historicalPe.ts` (guards non-positive EPS, correct median, no division
hazard), `client.ts` (every ticker goes through `encodeURIComponent`; errors carry only the
endpoint and HTTP status, so the API key cannot leak into a message the browser sees), the
DOM-id contract between `index.html` and `app.js` (all static and all 18 dynamically-built
scenario ids match), and every other `innerHTML` site (all numeric via `fmt()`). Fourth pass
also cleared: the CLI/server growth fallback chains (still byte-identical), NaN handling across
the wire (`JSON.stringify` turns NaN into null, so a garbage numeric input reaches the server as
null and the auto-seed runs correctly), and the CSS class inventory — every class used in
markup or JS has a rule except `panel-neutral` (`index.html:121`), which is cosmetic dead code,
recorded not fixed.

**Twelve Data's `income_statement` (quarterly) lags a real earnings release by at least ~10
days — FIXED with a cross-check warning, not a root-cause fix (root cause is upstream, outside
this app's control).** Found while independently verifying a user-reported CSCO EPS discrepancy
(app showed 3.08, five other sources — Gemini, Qualtrim, Investing.com, Finviz, Seeking Alpha —
all showed 3.33). Traced end-to-end against CSCO's own SEC filings: Cisco reported Q4 FY2026
(GAAP EPS $0.97) via 8-K on 2026-08-12; 13 days later `income_statement` still returned the stale
Q4 FY2025 quarter ($0.71) instead. Confirmed this is a genuine Twelve Data data-freshness gap, not
a bug in `resolveTtmEps`'s arithmetic (re-verified by hand against SEC XBRL) and not fixable by a
longer cache TTL (the *upstream* API itself was stale, not just this app's local cache) — live-
checked two days later (2026-08-25) and `income_statement` was *still* returning the same stale
quarter, while Twelve Data's own separate `statistics` endpoint (`trailing_pe`) and an independent
`yahoo-finance2` query had both already rolled forward. Since the root cause is outside this
codebase, fixed by adding a same-provider cross-check instead: `detectStaleTtmEps` (new,
`normalize.ts`) compares the `epsTtm`-implied trailing P/E against `statistics.trailing_pe` (a
faster-updating Twelve Data pipeline the app already fetched but only used as an inert reference
figure) and flags `StockData.staleTtmWarning` when they diverge >5%. Threshold was live-calibrated,
not guessed: two healthy cached tickers showed 1.5% (AAPL) and 0.04% (MSFT) divergence, while the
real stale CSCO case showed 7.3% — an initial 15% guess was checked against the live CSCO case
first and silently failed to fire, which is why it was recalibrated down to 5% rather than shipped
unverified. Surfaced in both the CLI (`formatOutput.ts`, a `⚠ WARNING` line under `EPS (TTM)`) and
the web UI (`app.js`, appended to the price-banner meta line with a `.stale-warning` CSS class).
3 new tests in `twelvedata/index.test.ts` (fires >5%, silent ≤5%, silent when provider figure is
missing) plus required-field fixes in 4 other test files that construct `StockData` mocks. 203/203
tests (was 200, +3 new), lint clean, build clean. Live-verified three ways: CLI against real CSCO
(warning appears) and real AAPL (no false positive); direct `POST /api/valuate` call
(`"staleTtmWarning":true` in the raw JSON); and the actual browser UI, where the price-banner meta
line read "CSCO · EPS (TTM) 3.08 · ... · ⚠ EPS (TTM) may be stale (diverges from provider trailing
P/E — check for a recent earnings release)". Note: this only catches the case where Twelve Data's
own `statistics` pipeline is ahead of its `income_statement` pipeline (true for CSCO, not
guaranteed for every stale-data cause) — a future session could still pursue a second, independent
source (`yahoo-finance2`'s `trailingEps`, confirmed live to have the fresh CSCO quarter via its
`mostRecentQuarter` field) as a stronger cross-check or an actual replacement `epsTtm` source when
Twelve Data is flagged stale, rather than only a warning.

**Known, accepted, not fixed** (low severity, documented rather than changed):

- `saveValuation`'s id is `Date.now()-TICKER`; two saves of the same ticker inside one
  millisecond collide, and the existing record is silently replaced.
- `getHistory` sorts by `new Date(evaluatedAt)`; a hand-edited record with a missing/garbage
  `evaluatedAt` yields a `NaN` comparator and an arbitrary order. `saveValuation` always sets
  the field, so this needs a hand-edited `history.json` to trigger.
- The CLI's `-m/--mos` runs through a bare `Number()`; a non-numeric value becomes `NaN`, which
  `calculateRuleOneValue` correctly rejects as `INVALID_MOS`, and `JSON.stringify` nulls on save.

**Test coverage:** `app.js`'s gap is closed — `renderGrowthTable`, `renderMultiplesTable`,
`renderGrowthChips`, `renderScenarioColumn`, `renderMethodCard`, `fetchHistory`,
`handleSaveValuation`, and the `fmt`/`fmtPercent`/`formatDate` helpers all now have direct
tests. 184 tests total (was 138 at the start of the day).

**This machine's `Z:` drive (Windows) is an SSHFS mount of the same filesystem this project
lives on, and its Windows driver returns `EPERM` instead of the POSIX-standard `EEXIST` when
something calls `mkdir` on a directory that already exists** — breaks `npm install`/`test`/
`lint`/`run web` and Claude Code's own file-write tooling (the `Edit` tool specifically; `Write`

- plain shell `cp`/`sed` work fine) from that path. On top of that underlying bug, the `Z:`
  mount can also drop out entirely under load (observed across multiple sessions, likely a side
  effect of opening/closing several SSH tunnels back-to-back) — when that happens even `cd` into
  the project fails until the mount reconnects on its own or is remounted.

**Workaround that resolved it this session:** SSH directly into the host instead of going
through the Windows SSHFS mount (`ssh aviv@100.76.172.46`, key-based, then
`cd shared_disk/Cursor_apps/Eps_Evaluation`). Same filesystem, same files, native Linux `mkdir`
semantics — `npm install`/`test`/`lint`/`build`/`web` all work normally there, independent of
whatever state `Z:` is in. `.claude/hooks/stop-test-gate.sh`'s `TEST_CMD` now routes through
this same SSH hop (commit `0d6082b`) so the stop-gate verifies against the real, working
environment instead of the broken local one. For file edits specifically, when the `Edit` tool
fails with `EPERM: operation not permitted, mkdir ...`, write the new content to the scratchpad
directory with `Write`, then `cp` it over the target path on `Z:` via the `Bash` tool (plain
shell operations on `Z:` work fine) — `sed` in-place on `Z:` also works for small mechanical
changes and is faster when applicable.

## Next up

1. The implementation is otherwise complete: the app covers the EPS×multiple valuation flow with
   two independent data sources (Twelve Data fundamentals + Yahoo analyst consensus) and a
   hierarchy-aware web UI.
2. ~~`npm audit` reports 8 known vulnerabilities~~ — **resolved.** Re-checked 2026-08-23:
   `npm audit` now reports 0 vulnerabilities (fixed by the 2026-08-16 `npm audit fix --force`
   upgrade of fastify/@fastify/static/vitest). Kept here only so the stale claim isn't
   re-flagged by a future session.
3. ~~Open bugs from the 2026-08-23 audit~~ — both fixed, see "Known problems" above. What
   remains is the `app.js` coverage gap listed there, not a known defect.

## Log

- 2026-08-14 — Bootstrapped repo with the CodeFundation starter kit.
- 2026-08-14 — Planned and implemented the full app (data layer, valuation layer, CLI, web)
  across tasks 1-9. 66/66 tests passing.
- 2026-08-15 — API key configured; ran end-to-end check against the live API, found and fixed
  two plan-tier issues (`growth_estimates` 403, `income_statement` outputsize cap) plus a port
  collision. 67/67 tests passing. Committed (`7821413`).
- 2026-08-15 — Redesigned web UI (price banner, growth-sources panel, valuation-multiples
  panel) per user feedback on a screenshot. Diagnosed the `Z:` SSHFS `mkdir`/`EPERM` bug,
  worked around it via direct SSH to the same host. 67/67 tests, lint, build clean; visually
  verified. Committed (`b889721`).
- 2026-08-15 — User flagged historical-5y growth, analyst-5y growth, and avg-P/E were still
  `n/a`. Confirmed live against Twelve Data's own `api_usage`/error messages that this is a
  Pro-vs-Ultra/Enterprise plan-tier gap, not fixable in code. Explored LLM-based alternatives
  (Gemini CLI — broken, Google-side auth migration issue; Codex CLI — works but is an
  unsourced-guess LLM, rejected as a data source) before settling on `yahoo-finance2`, a real
  sourced API. Built `src/data/yahoo/` (index/client/types + 6 tests), wired it into
  `src/web/server.ts` in parallel with graceful degradation, added 3 more server tests (75/75
  total), and added a third "Analyst consensus" UI panel. Lint/build clean; live-verified in a
  browser against MSFT (Strong Buy, next-year growth 19.53%, price targets shown with %
  upside/downside). Also fixed `.claude/hooks/stop-test-gate.sh` to route `TEST_CMD` through
  SSH instead of local `vitest` (commit `0d6082b`), since the local `Z:` environment can never
  self-repair its `node_modules`. Flagged (not fixed) 8 pre-existing `npm audit` CVEs in
  fastify/vitest as a separate background task. Committed (`4a2bd07`).
- 2026-08-15 — User flagged `Historical, 5Y` and `Avg. P/E` (1y/3y/5y) still `n/a` even with
  the Yahoo analyst panel live. Confirmed live the real ceiling is `income_statement`'s
  quarterly `outputsize` capping at 6 (not 4). Consulted the sibling `EvalApp` project
  (`D:\Investment Codes\EvalApp`) for its equivalent calc, ported its annual-EPS +
  median-with-`ceil(N/2)`-floor approach into `historicalPe.ts`, and added a local 5y-CAGR
  fallback for `historical5yPercent`. 77/77 tests, lint, build clean; live-verified against
  AAPL. Committed (`4d54b50`). Then redesigned the three panels per user feedback ("feels
  cramped") — primary/reference visual hierarchy via top-border accent + opacity, bar-fill
  visualization on growth-source rows, more row breathing room. Verified live in light/dark and
  desktop/mobile. Committed (`2d116c7`).
- 2026-08-16 — Ran `/code-review` on `85aeeed` (method-identity colour fix): no findings; the
  palette swap is correct and all three theme blocks were updated consistently. Then ran a full
  project re-evaluation comparing every documentation claim against the implementation. Baseline
  re-verified green via the SSH host (77/77, lint, build). Found no bugs in running code, but
  real documentation drift — chiefly that `src/data/yahoo/` (added in `4a2bd07`) and the
  `historicalPe` annual/median rewrite (`4d54b50`) were never reflected in `CLAUDE.md`. Wrote
  `docs/Project_ReEvaluation_2026-08-16.md` (findings + evidence), `TASKS.md` (8 prioritised
  tasks), and `docs/IMPLEMENTATION_PROMPT.md` (hand-off prompt for the model that will implement
  tasks 1-5, carrying the full working protocol and the three environment traps). Task 6 left
  open pending a product decision by the user.
- 2026-08-16 — Built `wiki/` (7 Hebrew pages) as a project-specific wiki, per user request.
  Verified the original "CodeFundation wiki" `.claude/standards/*.md` cite as their source is
  not reachable from this repo/environment (no URL, no local copy) before starting, so the new
  `wiki/` is built fresh from what this session verified in the code — not a recovery of the
  external one. Content deliberately reflects the corrected facts from the re-evaluation above
  (e.g. `src/data/yahoo/`, the annual/median `historicalPe`) rather than repeating `CLAUDE.md`'s
  current drift.
- 2026-08-16 — Completed tasks 1-5 from TASKS.md (documentation drift fixes). Task 6 is pending a product decision regarding the CLI/web analyst-consensus divergence.
- 2026-08-16 — Completed task 7 (created `README.md` with installation/usage instructions) and task 8 (added test coverage for `src/data/yahoo/client.ts`, `src/cli/index.ts`, and `src/web/public/app.js` using jsdom). 88/88 tests passing. Also addressed 8 security vulnerabilities by running `npm audit fix --force`, upgrading Fastify, @fastify/static, and vitest to new major versions. Verified that the app and test suite still function correctly post-upgrade.
- 2026-08-19 — Added valuation persistence and historical tracking feature:
  - Created `src/history/` (`types.ts`, `store.ts`, `index.ts`, `index.test.ts`) with disk persistence in `history.json` and full error handling.
  - Added REST endpoints in Fastify (`GET /api/history`, `POST /api/history`, `DELETE /api/history/:id`) with server tests in `src/web/server.test.ts`.
  - Added Web UI features: "Save this valuation" button, "Saved Valuations" interactive table with live filtering, "Load into form" feature, and "Delete" action.
  - Added CLI `--save` and `--history [TICKER]` flags with formatted terminal table output.
  - 99/99 tests passing, ESLint clean, TypeScript build clean.
- 2026-08-19 — Added Offline Caching, Margin of Safety (MoS), Notes & Thesis, and Scenarios features:
  - Created `src/data/cache.ts` and `src/data/cache.test.ts` providing transparent offline caching in `cache/` for Twelve Data and Yahoo API responses, gracefully falling back to cached fundamentals if offline or API subscription is inactive.
  - Added user-selectable Margin of Safety (`mosPercent`, 0%, 10%, 25%, 50%) to `src/valuation/ruleOne/index.ts`, Web UI dropdown, and CLI (`-m, --mos <percent>`).
  - Added Investment Thesis / Notes field in Web UI and CLI (`-n, --notes <text>`) persisted in `history.json` and displayed in historical valuation views.
  - Added Bull / Base / Bear scenario switch buttons in Web UI for quick assumption testing and real-time fair value recalculation.
  - 110/110 tests passing, ESLint clean, TypeScript build clean.
- 2026-08-21 — Re-evaluated the project (2nd pass) and re-synced documentation: ran the
  `/re-evaluate-project` skill via two parallel Explore agents plus direct verification; found
  the 2026-08-19 cache/history/MoS work was never folded into `CLAUDE.md` or `wiki/` — most
  notably `CLAUDE.md` still claimed "no mocked/offline mode" which the disk cache now
  contradicts. Wrote `docs/Project_ReEvaluation_2026-08-21.md` (full findings) and a designed
  PDF summary (`docs/Project_ReEvaluation_2026-08-21_Summary.pdf`, Hebrew/RTL via
  reportlab+python-bidi). Then updated `CLAUDE.md` (Architecture: added `src/data/cache.ts` and
  `src/history/`, fixed the offline-mode claim, documented `mosPercent`/new REST
  endpoints/CLI flags, added the `CACHE_DIR_PATH`/`HISTORY_FILE_PATH` env vars to Gotchas),
  `.env.example` (added those two vars, commented-out like `PORT`), and `wiki/` (`Home.md`,
  `ארכיטקטורה.md`, `מקורות-נתונים.md`, `שיטות-הערכה.md` updated; new page
  `wiki/היסטוריית-הערכות-ומטמון.md` added for the history/cache features — kept separate from
  the pre-existing `היסטוריה-ומקורות.md`, which is about commit history, not `src/history/`).
  The stop-test-gate hook then caught pre-existing (uncommitted, unrelated to this session's
  own edits) drift between `AnalystConsensus`'s type (`beta`/`priceToSales`/`ruleOf40` fields)
  and three test fixtures that predated them (`src/data/yahoo/client.test.ts`,
  `src/data/cache.test.ts`, `src/data/yahoo/index.test.ts`, `src/web/server.test.ts`) — fixed
  all four inline (test expectations/fixtures only, no production code changed). Baseline
  re-verified via SSH: 113/113 tests, lint clean, build clean (`tsc` had been silently broken
  before this fix — `npm test` alone doesn't type-check, so it wasn't caught by the git-status
  baseline check either).
- 2026-08-21 — Audited all valuation calculations (correctness, reliability, results) at user
  request. Verified by hand: Lynch (`eps * growth`), Rule #1 (EPS projection × exit P/E,
  discounted once), MoS discount, `clampGrowthRate`, `resolveTtmEps`, `calculateCagrPercent`,
  and `historicalPe`'s median-of-window logic all match their tests and their documented
  formulas exactly — no bugs found in the pure `src/valuation/`/`src/data/twelvedata/`
  calculation layer. Found two real bugs in `src/web/server.ts`'s growth-rate auto-fill logic
  (added 2026-08-19, untested, silently diverged from the CLI's fallback chain): (1) when no
  growth source was available at all, it defaulted `effectiveGrowth` to `0` instead of leaving
  it `null`, producing a fabricated $0 fair value with `ok: true` and no error shown, instead of
  the `MISSING_GROWTH_RATE` error the CLI correctly returns for the same situation; (2) an
  undocumented `Math.min(hist, 15)` capped the historical-growth fallback at 15% on the web only
  — not on the CLI, not in CLAUDE.md/wiki, not covered by any test — so identical data could
  produce fair values differing by up to ~47% depending on which adapter was used. Per user
  triage: bug (1) fixed but deprioritized (return null, not urgent); bug (2) fixed as the
  significant one (cap removed entirely). `server.ts` now uses the exact same fallback chain as
  `cli/index.ts` (`analystEstimate5y ?? historical3y ?? historical1y`, no cap, no default-to-0).
  Wrote two failing-then-passing tests in `server.test.ts` reproducing both bugs before fixing
  (per CLAUDE.md's bug-fix policy); updated the stale explanatory comment in `app.js`. 115/115
  tests (both new), lint clean, build clean, verified via SSH. Then verified the fix live end-
  to-end (not just unit tests): restarted the SSH-hosted web server (the first live check hit a
  stale pre-fix process — a red herring, not a regression), hit `/api/valuate` directly for
  real tickers, and drove the actual browser UI. NVDA (real historical 3Y growth 204.24%, no
  analyst estimate) now correctly uses the uncapped value before the standard [-5,25] clamp
  applies; RKLB (a real ticker with all four growth fields null on this plan tier) now shows
  "n/a — FAILED (MISSING_GROWTH_RATE)" in the UI instead of a fabricated $0.
- 2026-08-21 — Audited the three newly-added analyst-consensus fields (`beta`, `priceToSales`,
  `ruleOf40` in `src/data/yahoo/`) at user request. `beta`/`priceToSales` are direct pass-
  through from Yahoo's `summaryDetail` module, no local math, correct field mapping (live-
  verified: AAPL beta 1.09/P-S 9.65, NVDA beta 2.22/P-S 20.57 — both sane). `ruleOf40 =
(revenueGrowth + ebitdaMargins) * 100`: initially looked suspicious (NVDA showed 150.5%) but
  hand-verified against Yahoo's raw fields (revenueGrowth 0.852, ebitdaMargins 0.65294 — both
  already fractions) confirms the arithmetic and the result is a real, correct Rule of 40 score
  for a company with NVDA's actual growth/margin profile; AAPL's 52.4% is likewise sane. The
  null-guard correctly treats a genuine `0` in either field as real (not the falsy-zero bug
  this codebase specifically guards against elsewhere). Found and fixed one real bug:
  `app.js`'s "Financial Health" section-header check used `beta !== undefined || ruleOf40 !==
undefined`, but both fields are typed `number | null` and never actually `undefined` — so the
  header rendered even when both were genuinely `null`, producing an empty section for any
  ticker Yahoo has no financial-health coverage for. Fixed to check `!== null` (matching the
  row-level guards on the same lines already). Added 10 new tests (0 existed before for any of
  the three fields): 3 in `app.test.js` exercising `renderAnalystTable` directly (both-present,
  ruleOf40-only, both-null-no-header — the regression case), 7 in `yahoo/index.test.ts`
  (summaryDetail extraction, missing-summaryDetail nulling, ruleOf40 arithmetic against the
  real NVDA-shaped numbers above, the falsy-zero guard, and three missing-field null cases).
  125/125 tests, lint clean, build clean, verified via SSH.

- 2026-08-22 — Redesigned Web UI to display 3 scenarios (Base, Bear, Bull) side-by-side simultaneously instead of using toggle buttons.
  - Refactored backend src/web/server.ts to calculate and return all 3 scenarios (ase, ear, ull) in a single request for both Lynch and Rule #1 methods.
  - Updated src/history/types.ts to support nested scenario objects for saving history records while maintaining backward compatibility with old records.
  - Removed scenario state management and toggle listeners from src/web/public/app.js and updated DOM rendering logic to populate the 3-column grid structure.
  - Modified history table rendering to display 3 rows per saved valuation.
  - Applied CSS grid styling in src/web/public/style.css for the 3-column method cards and history table rows.
  - Updated wiki documentation (wiki/היסטוריית-הערכות-ומטמון.md and wiki/ארכיטקטורה.md) to reflect the new scenario generation logic and history persistence structure.
- 2026-08-22 — Reviewed the 3-scenario feature above at user request ("בדוק את התוספת, ג'מיני
  קידד") and found it was not actually done, despite the log entry above claiming completion:
  `npm run build` failed outright (3 TS18048 errors in `cli/index.ts`'s `formatHistoryOutput`,
  which still read the now-optional legacy `SavedValuation` fields directly), and 4/125 tests in
  `server.test.ts` failed against the new nested `{base,bear,bull}` response shape the tests were
  never updated for. Worse than the build break: **bear/bull's exit-P/E, required-return, and MoS
  were hardcoded constants in `server.ts` (10/15/50, 20/12/10) that silently ignored whatever the
  user actually typed into the form** — changing "Req. return" in the UI only ever affected the
  base scenario; the same three hardcoded numbers were independently duplicated a second time in
  `app.js` (history-save payload and the rule-one extras renderer), a second source of drift.
  User confirmed the fix direction (three separate input rows, one per scenario, not a return to
  the old toggle-button UX) and fixed root cause rather than papering over it:
  - `index.html`/`style.css`: replaced the single Exit P/E/Req.return/MoS row with a 3-row
    `scenario-assumptions` table (Bear/Base/Bull, each with its own Exit P/E, Req. return, MoS
    inputs, defaulting to the old hardcoded values so behavior is unchanged until the user edits
    them). Growth stays a single shared/derived field per user's explicit choice, not split per
    scenario.
  - `server.ts`: `ValuateRequestBody` gained `bear*`/`bull*` fields; bear/bull's
    `calculateRuleOneValue` calls now read them (`?? <old default>` only as a fallback for
    older/legacy clients that omit them) instead of hardcoding 10/15/50/20/12/10.
  - `app.js`: wired the new inputs into the `/api/valuate` POST body; removed both hardcoded
    duplicate copies of the bear/bull constants, replacing them with the server-echoed
    `result.inputs` (falling back to the actual current form values, never a hardcoded number);
    fixed a `|| null` that would have wrongly treated a real `0%` growth rate as missing (should
    have been `??`); wired the "Load" history button to also restore a saved record's bear/bull
    row values.
  - `cli/index.ts`: `formatHistoryOutput` now reads `r.base ?? r` before falling back to
    per-field `?? 'n/a'`, so it renders correctly for records saved by either the old (legacy
    flat fields) or new (`base`/`bear`/`bull`) shape — fixes both the TS compile error and the
    actual broken CLI `-H` output for any valuation saved through the web UI.
  - `style.css`: `.history-row-bear`/`.history-row-bull` used hardcoded raw `rgba()` colors that
    wouldn't adapt in dark mode; switched to `color-mix(in srgb, var(--bad|--good) 4%, transparent)`
    matching the theme-token convention every other rule in the file follows.
  - `server.test.ts`: fixed the 4 tests broken by the nested response shape
    (`body.lynch.fairValue` → `body.lynch.base.fairValue`, etc.), and added 2 new regression
    tests: one asserting bear/bull actually use request-provided exit-P/E/req.return/MoS (not
    the old hardcoded numbers — the specific bug this session fixed), one asserting the
    fallback-to-defaults path still works when a request omits the new fields.
  - Verified: 127/127 tests (was 121/125 broken), lint clean, build clean (was broken), and a
    live end-to-end browser check — set Bear's exit-P/E to 5 and required-return to 25%
    (deliberately not the old defaults), submitted a real AAPL valuation, confirmed the
    rendered "inputs used" text and the resulting fair value both reflect the custom values
    (not 10/15), then saved to history and confirmed the persisted JSON record carries the same
    custom bear values, and confirmed `npx tsx src/cli/index.ts -H AAPL` renders that
    same web-saved record correctly alongside pre-existing legacy-shaped records with no crash.
- 2026-08-23 — Ran `/code-review` on the uncommitted `app.js`/`app.test.js` changes (EPS field
  locked as display-only; bear/bull growth backfill + history-save switched from
  `growthRatePercentClamped` to `growthRatePercentRaw`). The change itself is correct — the
  raw-vs-clamped switch fixes a real asymmetry, since base saves `effectiveGrowth` (pre-clamp)
  while bear/bull were saving the clamped value, which would pin those scenarios to the
  clamp boundary (25/-5) on the next submit. 3 minor findings, none blocking: (1) the history
  "Load" button at `app.js:499` still writes `item.epsOverride` into the now-locked EPS field
  (harmless — `handleSubmit` overwrites it with `data.epsTtm` — but dead-by-intent, since no
  web-saved record can carry `epsOverride` anymore); (2) `currentValuation.epsOverride` at
  `app.js:714` is now permanently `undefined` and silently dropped by `JSON.stringify`, so the
  property is assembled as if it still carried meaning — cleaner to remove it; (3) the new
  lynch-fallback comment at `app.js:727` reads as a broad safety net but only actually fires
  for ruleOne-exclusive errors (`INVALID_EXIT_PE` etc.), since both methods share identical
  EPS/growth guards — the branch is correct, the comment oversells its scope.
  **All three fixed in the same pass:** the Load handler no longer touches the locked EPS
  field; `epsOverride` is gone from both the POST body and `currentValuation` (the local
  `const epsOverride = undefined` indirection removed entirely — an absent field already means
  "use data.epsTtm" server-side), with `renderHistoryTable`'s legacy-record display path left
  untouched; and the fallback comment now states its actual (narrow) scope. Added a regression
  test for the Load path that asserts **synchronously**, before the `handleSubmit()` the
  handler kicks off can repaint the field — an assertion after the await passes either way,
  which is exactly why the old behaviour looked harmless. Confirmed the test genuinely fails
  when the fix is reverted, then restored. 138/138 tests (was 137, +1), lint clean, build
  clean, all via the SSH host.
- 2026-08-23 — Re-confirmed the `Z:`-drive test blocker and documented the SSH workaround in
  `CLAUDE.md` (Commands + Gotchas), which previously claimed `npm test` worked unqualified.
  Note for future sessions: the repo **is** present on the SSH host at
  `~/shared_disk/Cursor_apps/Eps_Evaluation` (same filesystem `Z:` mounts) — there is nothing
  to copy, just `cd` and run. A first attempt this session wasted a tarball+scp round-trip
  after a too-shallow `ls ~/Eps_Evaluation ~/*Eps*` missed the nested path. Also confirmed the
  LAN address `192.168.1.224` is NOT reachable on port 22 from this machine (times out); only
  the Tailscale address `100.76.172.46` works. Suite verified in place: 137/137 across 15 files.
- 2026-08-23 — Audited the project for completeness/correctness at user request ("האם התוכנה
  שלימה וללא באגים?"). Baseline confirmed green (138 tests, lint, build, and `npm audit`
  now reports **0 vulnerabilities** — the "8 pre-existing CVEs" noted under "Next up" is stale
  and was resolved by the 2026-08-16 `npm audit fix --force`). Found two real pre-existing bugs
  and one coverage gap, all recorded under "Known problems" above; the headline one is that
  `POST /api/valuate` has **no runtime input validation** and returns raw 500s for a missing,
  null, or non-string `ticker` — verified live via `app.inject`, not inferred. Nothing found
  in the valuation math or the data layer. Answer given to the user: the app is feature-complete
  and its core is sound, but "ללא באגים" is not a claim the evidence supports.
- 2026-08-23 — Fixed both bugs from the audit above, failing-test-first per the bug-fix policy.
  (a) `POST /api/valuate` now validates `ticker` is a non-empty string before reaching the data
  layer — `ValuateRequestBody` is a TS interface, compile-time only, so a missing/null/numeric
  ticker previously threw inside `fetchStockData` and surfaced as a raw 500 leaking
  "ticker.toUpperCase is not a function". 6 new tests (5 malformed shapes + one asserting a
  valid `"  aapl  "` still works). Worth noting for future sessions: the new tests fail with
  **200, not 500**, because `fetchStockData` is mocked in `server.test.ts` — the real 500 only
  happened in the unmocked data layer, which is exactly why this gap survived a green suite.
  Verified the real path separately with an unmocked `app.inject` probe: all 6 malformed shapes
  now return typed 400s. (b) `renderPriceDelta`'s missing zero-denominator guard, plus a second
  identical site the fix-audit uncovered — `priceTargetValue`, feeding the analyst table's
  target rows — both of which rendered `+Infinity%` for a 0 price. 3 new tests. Confirmed each
  of the three new guards genuinely fails when reverted, then restored. 147/147 tests (was 138,
  +9), lint clean, build clean.
- 2026-08-23 — Closed the `app.js` test-coverage gap and then ran a line-by-line audit, per
  user request. Coverage: exposed the previously-untested render/fetch/save functions to the
  jsdom harness and added 34 tests covering them; one of those tests failed on first run and
  turned out to be a real bug (`priceToSales !== undefined`, item 3 above) rather than a bad
  assertion. Audit: read the valuation layer, `normalize.ts`, `cache.ts`, `history/`, the CLI
  argument handling, and the server endpoints line by line, probing behaviour with live
  `app.inject` calls rather than reasoning from the source alone. Found and fixed two more real
  bugs (the `NaN` CAGR shadowing valid growth data, and the cache path traversal) and recorded
  three low-severity issues as accepted rather than silently fixing them. Each of the three new
  guards was confirmed to fail its test when reverted, then restored. 184/184 tests, lint
  clean, build clean, all verified over SSH.
- 2026-08-23 — User asked whether the code is bug-free apart from the three accepted issues.
  Rather than answer from memory, audited the files not yet read line by line (`historicalPe.ts`,
  `client.ts`, `index.html`, the DOM-id contract, and every `innerHTML` site) — and found a
  **fourth real bug, the most serious of the day: HTML injection through `recommendationKey`**,
  in `app.js`, a file already audited twice. Confirmed in jsdom that the payload becomes a live
  `<img onerror=...>` element, then fixed `tableRow` to render text by default. Answer given:
  no, "bug-free" is still not a supportable claim — each deeper pass has found something the
  previous one missed, including in files previously declared clean. 187/187 tests, lint clean,
  build clean.
- 2026-08-23 — Fourth audit round at user request. Deliberately targeted what single-function
  review structurally cannot catch: async/state behaviour, cross-file contracts, and the CSS
  inventory. Found two more real bugs — the stale-response race (items 5) and the `null`
  history record (item 6) — both reproduced with failing tests first, both guards confirmed to
  fail when reverted. The race is the notable one: it is invisible to any per-function review
  because every function involved is individually correct; only the interleaving is wrong.
  189/189 tests, lint clean, build clean.
- 2026-08-23 — Fifth audit round, aimed at the one area repeatedly named as unexamined: real
  API data rather than code reading. Ran both valuation methods across all 26 cached tickers
  and diffed the outputs for anything non-finite or nonsensical. That surfaced item 7 — a
  negative dollar fair value shipped as a valid result — which four passes of line-by-line
  review had not found, because every line of `calculateLynchValue` is individually correct;
  only the formula's DOMAIN was wrong. Also confirmed via the same sweep that the three
  loss-making tickers in the cache (IONQ/RKLB/ZETA, all with negative EPS) correctly return
  NEGATIVE_OR_ZERO_EPS, and that no cached record carries a non-finite number. Per user
  decision, chose the error over clamping to 0 (a $0 fair value still reads as a real
  valuation). 192/192 tests, lint clean, build clean.
- 2026-08-23 — Ran `/code-review max` (deep, line-by-line, fork-run) on the uncommitted
  `fix/locked-eps-raw-growth` diff (the branch's own 7 commits vs. `main`; the other ~38 files
  git showed as "modified" were pure CRLF/file-mode noise with zero real content diff, excluded
  from scope). Found 14 issues; the two most severe were live-verified crashes, both ironic in
  the same way: the diff's own stated purpose was to close exactly these failure classes, and
  both survived because the diff's own new tests couldn't reach the real failure path. (1)
  `POST /api/valuate` destructured `request.body` _before_ the new ticker-validity guard ran, so
  a bodyless POST or a literal JSON `null` body still threw an unhandled 500 -- none of the new
  tests sent a body-less/null request, only well-formed objects with a bad `ticker` field. (2)
  `readHistoryFile`'s new corruption filter only checks that `ticker` is a string; a record
  missing `currentPrice` passed it but crashed the CLI's `formatHistoryOutput` at an unguarded
  `r.currentPrice.toFixed(2)` -- the exact "one corrupt entry loses the whole listing" bug this
  diff claimed to fix, via a narrower malformed shape than the tests covered (the web UI was
  unaffected, since `renderHistoryTable` already routes through the null-safe `fmt()`).
  User asked to fix all 14. Fixed in this pass (test-first per policy, all verified live in
  addition to the new/updated unit tests):
  - `server.ts`: guards `request.body` before destructuring (typed 400, not a raw 500, for a
    missing/null body); the ticker guard now normalizes (trim + uppercase) and validates format
    via `cache.ts`'s newly-exported `safeTickerSegment` -- the exact same rule the cache uses to
    build filenames, so a ticker that clears this boundary can never silently skip caching the
    way a space-containing ticker previously could; `fetchStockData`/`fetchAnalystConsensus` now
    receive the normalized ticker, not whatever whitespace/casing the caller sent.
  - `server.ts` + `app.js`: the server now echoes `bearGrowth`/`bullGrowth` (the value actually
    used for those scenarios) in the response, unconditionally -- same pattern as the existing
    `effectiveGrowth`. This fixes a real bug the frontend had no way to fix on its own: when
    ruleOne fails for an unrelated reason (e.g. an emptied exit-P/E) _and_ lynch simultaneously
    fails for a different unrelated reason (that same growth being negative), neither
    `ValuationResult` carries an `inputs` field to recover the number from, even though a real
    value was computed and used server-side. Collapsed 4 near-identical duplicated fallback
    expressions in `app.js` down to reading `body.bearGrowth`/`body.bullGrowth` directly.
  - `cli/index.ts`: `formatHistoryOutput` no longer assumes `currentPrice` is a number, matching
    how every other optional field in that function is already treated.
  - `cache.ts`: exported `safeTickerSegment` (see above) and removed a redundant `!upper.includes('..')`
    check the charset regex already made impossible (no `/` is ever accepted, so a literal `..`
    can only ever become the harmless filename `twelvedata_..json`).
  - `history/store.ts`: a dropped malformed entry now logs a `console.warn` -- it was silently
    and permanently erased from history.json on the next unrelated save/delete's read-modify-
    write, with nothing surfacing that a row had been lost.
  - `app.js`: extracted a shared `isValidPrice()` predicate (`renderPriceDelta` and
    `priceTargetValue` had duplicated, inverted copies of the same zero-price guard); `setLoading`
    now reuses the existing module-level `refreshBtn` binding instead of a second
    `getElementById('refresh-btn')` call; added the missing `fetchHistory` response-sequencing
    guard (`latestHistoryRequestId`), the same race class `latestValuateRequestId` already guards
    against for `/api/valuate`, previously left open in the history ticker filter.
  - Test fixture gap closed: `app.test.js`'s DOM fixture never defined `#refresh-btn`, so the
    "disable Refresh Live while loading" mechanism above had zero coverage -- deleting it would
    not have failed any test, including the concurrent-requests race test. Added the element and
    a regression test.
  - Left unchanged, by design: the `NEGATIVE_GROWTH_RATE` guard stays inline in
    `calculateLynchValue` rather than moving to a shared validator -- only one caller needs it
    today, and CLAUDE.md's own simplicity principle ("no abstraction until variation is real")
    argues against extracting a home for it before a second EPS×growth method exists.
    Verified: 200/200 tests (was 192, +8 new), lint clean, build clean, all via the SSH host. Two
    headline fixes additionally confirmed live (not just via the mocked test suite): a real running
    server now returns typed 400s for a bodyless/null-body POST and for a `/../`-containing ticker
    instead of a raw 500; a hand-written `history.json` entry missing `currentPrice` now renders as
    `n/a` in `npx tsx src/cli/index.ts -H` instead of crashing the entire listing.
- 2026-08-25 — User reported CSCO's EPS TTM didn't match a site they trust (3.33 vs. the app's
  3.08, a ~10% gap) and asked for it to be verified by calculation, not assumption. Extensive
  live investigation (SEC EDGAR XBRL + 8-K/10-Q/press-release cross-checks, not guesswork) across
  five independent third-party sources (Gemini, Qualtrim, Investing.com, Finviz, Seeking Alpha —
  all converging on 3.33) traced the root cause to real data staleness, not a methodology
  difference (GAAP vs. non-GAAP was the initial hypothesis and was ruled out): Cisco filed Q4
  FY2026 results (GAAP EPS $0.97) on 2026-08-12, but the app's Twelve Data-sourced cache, refreshed
  2026-08-23, still rolled in the now-superseded Q4 FY2025 quarter ($0.71) instead. Recorded as a
  new "Known problems" entry above (Twelve Data quarterly-earnings staleness, no detection in
  `resolveTtmEps`). No code changed this session — investigation and documentation only.
- 2026-08-25 (later same day) — User asked to verify the Twelve Data staleness claim more
  rigorously before trusting it, and to check whether yfinance/Alpha Vantage could serve as a
  cross-check. Re-confirmed live (not just the earlier snapshot): `income_statement` was *still*
  stale two days on; found a same-provider proof the earlier investigation missed — Twelve Data's
  own `statistics.trailing_pe` had already updated while `income_statement` had not, meaning the
  two pipelines inside Twelve Data itself disagree. Also queried `yahoo-finance2` live: its
  `trailingEps` (3.31) and `mostRecentQuarter` (2026-07-25, the exact stale quarter) confirmed Yahoo
  was current. Alpha Vantage's `demo` key doesn't support CSCO (confirmed live, would need the
  user's own registered key). Implemented the cross-check-warning fix described in "Known
  problems" above: `detectStaleTtmEps` in `normalize.ts`, `staleTtmWarning` on `StockData`, CLI
  and web UI surfacing. First attempt used a guessed 15% threshold; live-testing it against the
  real CSCO case immediately showed it doesn't fire (actual divergence was 7.3%), so recalibrated
  to 5% using two known-healthy tickers (AAPL 1.5%, MSFT 0.04%) as the noise floor before
  re-verifying live. 203/203 tests (was 200, +3), lint clean, build clean, verified live via CLI
  (both a firing and a non-firing real ticker), a direct API call, and the browser UI.
