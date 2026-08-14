# Project: Eps_Evaluation

## Commands

- Build: `npm run build` (`tsc -p tsconfig.json`)
- Test (all): `npm test` (`vitest run`)
- Test (single): `npx vitest run <path>`
- Lint: `npm run lint` (`eslint .`)
- Format: `npm run format` (`prettier --write .`)
- Run locally: `npm run cli -- TICKER` (e.g. `npm run cli -- AAPL`), `npm run web` (Fastify on `PORT`, default 3000)

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
  (e.g. `<domain>/<use-case>/` holding handler, validation, and its tests together).
- Depend on published interfaces only — never reach into another module's internals.
- A change should touch one slice and its tests. If it can't, say so before implementing.

### 3. Surgical changes
- Touch only what the task requires. Clean up only your own mess.
- Don't refactor unbroken adjacent code or "improve" what you happened to read.
- Match the existing style, even where you'd have chosen differently.
- Only remove dead code that your own change created.

## Verification policy

- Every change ends with its check passing: run the test command from **Commands** above
  (or the relevant single test) and show the output. If you can't verify it, don't call it done.
- Fix root causes. Never suppress an error, skip a test, or weaken an assertion to get green.
- For bug fixes: write a failing test that reproduces the issue first, then fix it.
- Performance work needs a stated budget and a measurement before any change (`perf-investigator`).
  "Faster" is not a budget, and an unmeasured optimization is just added complexity.

## Workflow

- Non-trivial changes (multi-file, unfamiliar code, uncertain approach): explore and plan
  first; skip planning for one-line fixes.
- Large features: `/spec` (interview → SPEC.md), then `/slice` (→ TASKS.md), then one task per
  fresh context via the `task-implementer` agent. Don't implement a feature nobody has scoped.
- For risky or multi-session work, start from a worktree on a new branch and confirm the
  suite is green BEFORE the first edit — then any later failure is attributable to this change.
- Before treating a feature as done, review the diff against the plan in a fresh context
  (`code-reviewer` agent or `/code-review`). Escalate when the change earns it:
  `architecture-reviewer` if it crosses module lines or adds a layer, `security-auditor` if it
  touches input handling, auth, files, shell, or dependencies.
- Commit with a descriptive message after each completed unit of work.

## Session log

`CURRENT_WORK.md` is the running work log for this project: what's done, what's in flight,
known problems, what's next. **Read it at the start of every session, before doing anything
else** — that's how continuity across sessions works without re-explaining context each time.
Update it whenever you plan, execute, or hit a problem: after finishing a unit of work, before
ending a session, and any time state changes enough that the next session would be misled by
a stale file. Never leave "In flight" pointing at something already finished or abandoned.

## Multi-session projects

Start every session with `/orient`: read git log + CURRENT_WORK.md, verify the baseline is
green, pick ONE feature, state the finish line. A red baseline is the session's work — don't
build on it. Complete one feature at a time. Leave the code mergeable — no half-done work
without a note in CURRENT_WORK.md. Run `/harness` once at the start of a project that will
span many sessions.

## Repository etiquette

- Branch naming: `feature/<slug>`, `fix/<slug>`
- Commit messages: imperative mood, one logical change per commit

## Gotchas

- None yet — this project has no code. Update this section as real quirks surface.
