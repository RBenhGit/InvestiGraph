---
name: spec
description: Interview the user about a feature and write a complete SPEC.md to implement in a fresh session
disable-model-invocation: true
argument-hint: [brief feature description]
---

The user wants to build: $ARGUMENTS

Interview them in detail using the AskUserQuestion tool. Ask about technical implementation, UI/UX, edge cases, error handling, and tradeoffs. Don't ask obvious questions — dig into the hard parts they might not have considered. Keep interviewing until the feature is fully pinned down.

Then write the spec to SPEC.md with exactly these sections:

1. **Goal** — the problem being solved and what success looks like, in the user's terms
2. **Scope** — what this feature includes, and an explicit **Out of scope** list
3. **Design** — the files and interfaces involved (name them), data flow, and how the feature fits the project's module boundaries; new code goes in its own slice
4. **Tasks** — small, isolated, testable units in implementation order (each one sentence, each verifiable)
5. **Edge cases & errors** — every case surfaced in the interview, with the decided behavior
6. **Verification** — the end-to-end check that proves the feature works: exact commands, example inputs, expected outputs

Keep the spec self-contained: someone with no memory of this conversation must be able to implement it.

After writing, tell the user: review/edit SPEC.md, then start a **fresh session** and prompt "Implement SPEC.md task by task; run the verification section when done." A clean context implements specs better than this conversation will.
