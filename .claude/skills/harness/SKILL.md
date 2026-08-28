---
name: harness
description: Set up the multi-session harness for a project that will outlive one context window — FEATURES.json, PROGRESS.md, and init.sh — so every future session can orient, verify, and finish clean
disable-model-invocation: true
argument-hint: "[project or milestone name]"
---

Set up the multi-session harness for: $ARGUMENTS

**Read `references/harness-files.md` (next to this file) first.** It carries the file formats, the
reasoning behind each choice (including why the feature list is JSON), and the failure modes the
harness exists to prevent.

This is a one-time setup skill. The per-session ritual is `/orient`.

## Procedure

1. **Check what already exists.** If `FEATURES.json`, `PROGRESS.md`, or `init.sh` are present,
   you are updating, not recreating — read them and preserve completed state. Never reset a
   `"passes": true` you did not verify yourself.

2. **Establish the environment launcher** (`init.sh`): the one command that brings the project up
   from a clean checkout — install, migrate/seed, build, run. Run it. If it fails, fix it or
   record precisely what a human must do; a harness whose launcher doesn't work is worse than none.

3. **Write `FEATURES.json`** using the reference's schema. Granular features, each with its steps
   and `"passes": false`, each with the command that decides `passes`. Derive them from SPEC.md or
   TASKS.md if either exists rather than inventing a parallel plan.

4. **Write `PROGRESS.md`** using the reference's template: current state, what was last completed,
   what is in flight, known problems, and the next feature to pick up.

5. **Add the orientation ritual to CLAUDE.md** — a short block telling every session to read git
   log → PROGRESS.md → FEATURES.json, verify the baseline with `init.sh`, take ONE feature, and
   leave the tree mergeable. Keep it under 12 lines; it loads on every request.

6. **Commit** the harness files as one commit. Git is the memory and the undo.

## Output

- The files created or updated, and the feature count
- The result of actually running `init.sh` (output, not a claim)
- The first feature the next session should pick up
- Anything you could not determine, listed as an explicit gap rather than a guess
