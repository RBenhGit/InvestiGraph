# Test Signal — auditing whether tests can actually fail

> **Provenance.** Distilled from the CodeFundation wiki pages `tdd-with-agents` and
> `verification-loops` (upstream: `fowler-maintainability-sensors`, `claude-docs-best-practices`,
> `anthropic-long-running-harnesses`, `obra-superpowers`).

## Contents

1. The problem this exists to catch
2. The probe (safe mutation testing by hand)
3. Weak-assertion patterns to grep for
4. Coverage as a signal, and its limit
5. Rules you may not break
6. Output format

---

## 1. The problem this exists to catch

Coverage measures *execution*, not *verification*. A test can run every line of a function and
assert nothing meaningful about the result. Agent-written tests are especially prone to this:
an agent that writes code and tests together will fit the test to the implementation.

The documented case: a file with **100% statement coverage and 13 surviving mutations** — thirteen
ways to break the code that no test noticed.

Your job is not to add coverage. It is to answer one question per test cluster:
**if the behavior under test broke, would this suite go red?**

## 2. The probe (safe mutation testing by hand)

If the project has a mutation-testing tool configured (Stryker, mutmut, cargo-mutants, PIT), run
it and report its surviving mutants — that is strictly better than probing by hand.

Otherwise, probe manually. **The safety protocol is not optional:**

1. **Snapshot first.** Run `git status --porcelain` and record it. If a file you intend to mutate
   already has uncommitted changes, do not touch it — probe elsewhere and say which files you
   skipped and why.
2. **Establish green.** Run the target tests and confirm they pass before mutating. A suite that
   is already red tells you nothing.
3. **One mutation at a time.** Apply a single mutation, run only the narrow test scope, record
   pass/fail.
4. **Revert immediately** (`git checkout -- <file>`) before the next mutation. Never batch.
5. **Verify clean.** Re-run `git status --porcelain` at the end and confirm it matches the
   snapshot from step 1. Show that output in your report.

**Mutations worth applying** (cheapest first, highest yield first):

| Mutation | What a survivor proves |
|---|---|
| Flip a boundary: `<` → `<=`, `>` → `>=` | Off-by-one is untested |
| Negate a condition: `if (x)` → `if (!x)` | The branch is executed but its effect is unasserted |
| Return a constant: replace a computed return with `0` / `""` / `null` | The test never inspects the value |
| Delete a side effect: remove a write, an emit, a save | The effect is assumed, never checked |
| Swap an operator: `+` → `-`, `&&` → `\|\|` | Arithmetic/logic is unverified |
| Remove an error path: delete a `throw` / early return | Error behavior is untested |

A mutation that **survives** (tests still pass) is a finding. A mutation that is **killed** is
evidence the test cluster has signal — report that too; it is the only way the report is
falsifiable.

## 3. Weak-assertion patterns to grep for

Cheap static pass before probing. Each of these is a candidate, not a verdict:

- Tests with no assertion at all — they only check "does not throw"
- Assertions on truthiness alone (`assert result`, `expect(x).toBeTruthy()`) where a value matters
- `expect(fn).toHaveBeenCalled()` with no argument or ordering check
- Snapshot tests committed without ever being reviewed (a snapshot regenerated on failure asserts
  nothing)
- Assertions on private internals rather than observable behavior — these fail on refactors and
  pass on real regressions
- `try/catch` swallowing inside a test
- Tests that assert on data they themselves computed with the same code under test
- Sleeps, and tests that depend on execution order — flaky signal is worse than no signal, because
  it gets muted

## 4. Coverage as a signal, and its limit

Use coverage only to find *unexecuted* code — it is a floor, never a ceiling. Report uncovered
paths that are reachable and consequential (error handling, boundary branches, new code in the
diff). Never recommend a coverage percentage target: it is the metric that produced the
100%-coverage/13-survivors case.

## 5. Rules you may not break

- **Never delete, skip, weaken, or rewrite an existing test to make anything pass.** In harness
  guidance this is a hard rule: "it is unacceptable to remove or edit tests because this could
  lead to missing or buggy functionality."
- Never leave a mutation in the tree. §2.5 is the check.
- Do not modify implementation code as a fix — you audit, you don't repair. Hand repairs to the
  test-writer or the implementer.
- Prefer the narrowest test scope that answers the question; a full-suite run per mutation makes
  the audit unaffordable and tells you no more.

## 6. Output format

- **Scope** — which test clusters and source files were audited, and which were skipped (§2.1)
- **Surviving mutations** — for each: `file:line`, the mutation applied, the test file that should
  have caught it, and the one-line assertion that would kill it
- **Killed mutations** — count, so the reader can judge the audit's strength
- **Weak assertions** — `file:line` and what the test should assert instead
- **Uncovered and consequential** — reachable paths with no test at all
- **Working tree** — the `git status --porcelain` output proving you left nothing behind
- **Verdict** — does this suite have enough signal to be trusted as the verification loop?
