# Task Execution Protocol

> **Provenance.** Distilled from the CodeFundation wiki pages `efficient-coding-foundation`,
> `long-running-agent-harnesses`, `verification-loops` and `spec-driven-development`
> (upstream: `obra-superpowers`, `anthropic-long-running-harnesses`,
> `claude-docs-best-practices`, `karpathy-skills-claude-md`).

## Contents

1. What one task is
2. The protocol
3. The four failure modes this prevents
4. Scope rules
5. Evidence rules
6. When to stop and report instead of continuing

---

## 1. What one task is

A task sized for a fresh context: **2–5 minutes of work, with exact file paths and a verification
step**. That granularity is what lets an agent with no memory of the planning conversation execute
without re-deriving context.

If the task you were handed is bigger than that, or its files are unnamed, or it has no stated
check — **do not start**. Report what is missing. An underspecified task executed confidently is
the most expensive failure available to you.

## 2. The protocol

1. **Orient.** Read the task, and only the task's stated inputs (spec section, plan item, files
   named). Read the neighbouring code you will change and one sibling example of the pattern you
   are meant to follow.
2. **Establish the baseline.** Run the task's verification command *before* changing anything and
   confirm it is green (or red for the expected reason, in TDD). A later failure is only
   attributable if the starting state was known.
3. **Implement the smallest change that satisfies the task.** Match the existing style, naming, and
   layout exactly, even where you would have chosen differently.
4. **Verify.** Run the check. Show the output. If it fails, fix the root cause and run it again —
   never suppress an error, weaken an assertion, skip a test, or broaden a catch to get green.
5. **Report.** Files changed, the check and its output, anything you noticed but did not touch,
   and what the next task should be aware of.

Steps 2 and 4 use the **same** command. If they can't, say why.

## 3. The four failure modes this prevents

Unharnessed long work fails in four documented ways. The protocol maps to them one for one:

| Failure mode | The step that prevents it |
|---|---|
| **Over-ambition** — context exhausted mid-feature, partial work undocumented | §1 sizing, §4 scope rules |
| **Premature completion claims** — "done" without a check | §2.4 evidence |
| **Insufficient testing** — units pass, the feature doesn't work | §2.2 baseline + end-to-end where the task names one |
| **Environmental degradation** — buggy or messy state left behind | §2.5 report + leave-it-mergeable |

Leave the tree mergeable. If you cannot finish, leave the code in a state that builds and passes,
and say exactly what remains — a half-finished task with an honest note is recoverable; a
half-finished task presented as done is not.

## 4. Scope rules

- **Touch only what the task requires.** Clean up only your own mess.
- Do not refactor unbroken adjacent code, rename things you merely read, or "improve" a file you
  happened to open.
- Only remove dead code that your own change created.
- Do not add abstraction, configuration, or generality the task does not need today. Minimum code
  that solves the problem; nothing speculative.
- If the task cannot be done without touching another module's internals, **stop and report** —
  that is a boundary problem, and a design decision that is not yours to make silently.
- Found a real bug outside your task? Write it down in the report. Do not fix it.

## 5. Evidence rules

- Show the command and its output — not a claim about it. "Reviewing evidence beats re-running
  verification yourself" is why the human asked for output rather than a summary.
- Include the failure output too, when a check failed before you fixed it. It is what makes the
  fix credible.
- For UI work, the evidence is a screenshot or an end-to-end run "as users would perform it";
  unit tests alone under-report breakage, and this must be done explicitly because it will not
  happen by default.
- If no check exists for what you changed, say so in one line. Do not invent a passing narrative.

## 6. When to stop and report instead of continuing

Stop after two failed attempts at the same fix. Accumulated corrections degrade the context you
are working in; a fresh attempt with what you learned beats a third correction in a polluted
window. Report:

- What you tried, and the exact failure each time
- What you ruled out, and the evidence that ruled it out
- What you would try next, and what information would decide it

Also stop and report — without proceeding — when the task contradicts the spec, when the named
files do not exist, when the baseline (§2.2) is already red for an unrelated reason, or when the
change would grow beyond one slice.
