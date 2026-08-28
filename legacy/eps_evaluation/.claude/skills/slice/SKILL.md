---
name: slice
description: Decompose a feature or SPEC.md into vertical slices and 2-5 minute tasks with exact file paths and verification steps, ready for fresh-context execution
disable-model-invocation: true
argument-hint: "[feature name, or path to SPEC.md]"
---

Decompose into an executable task list: $ARGUMENTS

**Read `references/vertical-slicing.md` (next to this file) before decomposing.** It defines what
a slice is, why horizontal phases are an anti-pattern, and the task-quality bar. The whole value of
this skill is in that bar — a list of vague tasks is worse than no list.

## Procedure

1. **Get the input.** If given a SPEC.md path, read it. If given only a feature name and no spec
   exists, say so and recommend `/spec` first — decomposing an unspecified feature just moves the
   guessing downstream. Proceed only if the user confirms.

2. **Read the codebase before slicing.** Find one existing slice that resembles the target and note
   its layout, naming, wiring, and test convention. Tasks that don't name real paths in the real
   structure cannot be executed by a fresh context.

3. **Cut vertical slices.** Each slice crosses every layer it needs (storage → logic → interface)
   and ends in something observable end to end. Never order the work by layer.
   Order slices so the earliest one proves the riskiest assumption.

4. **Break each slice into tasks** meeting the bar in the reference:
   - 2–5 minutes of work
   - exact file paths (existing, or new with the directory named)
   - a verification step that is a runnable command with an expected result
   - independent of tasks in *other* slices; ordered within its own slice

5. **Write `TASKS.md`** using the reference's template. Do not write code.

6. **Check the list against the reference's quality gate** and state the result. Fix anything that
   fails before handing it over.

## Output

`TASKS.md`, plus a short summary: the slices in order, the total task count, the riskiest
assumption and which slice proves it, and anything you could not decompose (with what would settle
it).

Then tell the user how to run it: one fresh `task-implementer` per task in order, or a fresh
session per slice — and review the diff (`code-reviewer` or `/code-review`) at each slice boundary,
not only at the end.
