# Vertical Slicing and Task Granularity

> **Provenance.** Distilled from the CodeFundation wiki pages `spec-driven-development`,
> `efficient-coding-foundation`, `agent-friendly-architecture` and `tdd-with-agents`
> (upstream: `claude-code-practice-handbook`, `obra-superpowers`, `github-spec-kit`,
> `maintainable-agentic-codebase`).

## Contents

1. What a vertical slice is
2. Why horizontal phases are an anti-pattern
3. The task bar
4. TASKS.md template
5. Quality gate
6. Common decomposition mistakes

---

## 1. What a vertical slice is

A slice is a **tracer bullet**: the thinnest change that crosses every layer it touches — storage,
logic, interface — and ends in behavior someone can observe. "Users can change their password with
their old password verified" is a slice. "The password data layer" is not.

Slices align with the architecture the rest of this kit assumes: a domain directory containing a
use-case directory that holds the entry point, validation, core logic and tests side by side. One
slice ≈ one directory ≈ one small test cluster. That correspondence is what keeps verification
narrow and the blast radius small.

Order slices so that **the earliest slice proves the riskiest assumption**. If something is going
to invalidate the design, it should do so in slice 1, not slice 6.

## 2. Why horizontal phases are an anti-pattern

Building the whole data layer, then the whole service layer, then the UI "delays end-to-end
feedback" — and end-to-end feedback is the signal the entire loop depends on. Until layers meet,
nothing is verifiable, nothing is demoable, and every assumption made in layer one stays unchecked
until layer three. This is listed explicitly as an anti-pattern in community practice, and it is
also the failure mode Spec Kit's task phase is designed to avoid: "create a user registration
endpoint validating email format", not "build authentication."

Each slice carries its own tests — unit, and integration or automation where the slice touches a
boundary. Testing is not a phase at the end.

## 3. The task bar

A task is executable by a **fresh context with no memory of the planning conversation**. That
constrains it in four ways:

| Requirement | Test |
|---|---|
| **2–5 minutes of work** | If it needs a decision mid-way, it's two tasks. If it takes 30 seconds, fold it into its neighbour. |
| **Exact file paths** | Every file named — existing paths verified, new paths with the directory stated. "Update the handler" fails. |
| **A runnable verification step** | A command and its expected result. "Verify it works" fails. If there is no command, name the manual check and its expected observation. |
| **Self-contained context** | Everything needed to execute is in the task or in a file it names. No "as we discussed". |

Sequencing rule: tasks are ordered *within* a slice; slices are ordered by risk. Two tasks in
different slices should not touch the same file — if they must, they belong in the same slice.

Bug-fix tasks invert step order: the first task writes a failing test that reproduces the bug,
the second makes it pass. That is the official pattern and it survives decomposition.

## 4. TASKS.md template

```markdown
# Tasks — <feature>

**Source:** SPEC.md (or: the request, quoted)
**Slices:** N   **Tasks:** M
**Riskiest assumption:** <what could invalidate the design> — proved by slice 1

## Slice 1 — <observable behavior in one sentence>
**Done when:** <the end-to-end observation that proves this slice works>

- [ ] **1.1** <action>
  - Files: `path/one.ts`, `path/two.test.ts` (new)
  - Verify: `<command>` → <expected result>
- [ ] **1.2** ...

## Slice 2 — ...

## Out of scope
<carried from the spec, so no task quietly re-adds it>

## Open questions
<anything that must be answered before the affected task runs, and who answers it>
```

## 5. Quality gate

Run this before handing the list over, and state the result:

1. Does every task name real paths? (Check them — a wrong path is a stalled task.)
2. Does every task have a command and an expected result?
3. Is any task longer than ~5 minutes, or does any require a decision to be made mid-task?
4. Does each slice end in something observable end-to-end?
5. Do two tasks in different slices touch the same file?
6. Could a stranger execute task 3.2 with only TASKS.md and the repo?

Any "no" is a defect in the list — fix it before execution, not during.

## 6. Common decomposition mistakes

- **Layer-shaped slices** — "the API layer" is a phase wearing a slice's name.
- **A setup slice** that builds infrastructure with nothing observable. Fold setup into the first
  slice that needs it.
- **Tasks that are really specs** — "handle errors appropriately" defers the decision to the
  implementer, which is the ambiguity a spec exists to remove.
- **Test tasks at the end** — a trailing "write tests" task is how suites end up fitted to the
  implementation.
- **Refactor tasks bundled with feature tasks** — separate them; they have different risk and
  different verification.
- **Over-decomposition** — twenty 30-second tasks cost more in orientation overhead than they save.
