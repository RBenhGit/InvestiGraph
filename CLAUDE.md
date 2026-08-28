# Project: {{PROJECT_NAME}}

<!-- Starter template from CodeFundation. Fill every {{...}}, delete what doesn't apply,
     keep the whole file under 200 lines. Per-line test: "Would removing this cause
     Claude to make mistakes?" If not, cut it. -->

## Commands

- Build: `{{BUILD_CMD}}`
- Test (all): `{{TEST_CMD}}`
- Test (single): `{{TEST_SINGLE_CMD}}`
- Lint: `{{LINT_CMD}}`
- Format: `{{FORMAT_CMD}}`
- Run locally: `{{RUN_CMD}}`

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
  (e.g. `{{DOMAIN}}/{{use-case}}/` holding handler, validation, and its tests together).
- Depend on published interfaces only — never reach into another module's internals.
- A change should touch one slice and its tests. If it can't, say so before implementing.

### 3. Surgical changes
- Touch only what the task requires. Clean up only your own mess.
- Don't refactor unbroken adjacent code or "improve" what you happened to read.
- Match the existing style, even where you'd have chosen differently.
- Only remove dead code that your own change created.

## Verification policy

- Every change ends with its check passing: run `{{TEST_CMD}}` (or the relevant single test)
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

- Branch naming: `{{BRANCH_CONVENTION}}`
- {{OTHER_ETIQUETTE}}

## Gotchas

- {{NON_OBVIOUS_QUIRK_1}}
