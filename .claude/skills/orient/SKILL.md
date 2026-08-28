---
name: orient
description: Start-of-session ritual for multi-session work — read the recent history and progress files, verify the baseline is green, and pick exactly one piece of work before making any change
disable-model-invocation: true
---

Orient before changing anything.

Recent history: !`git log --oneline -10`
Working tree: !`git status --short`

## Do this in order

1. **Read the state.** PROGRESS.md (or equivalent) and FEATURES.json (or TASKS.md / SPEC.md) if
   they exist. Combined with the log above, that is the previous shift's handover — read it before
   forming any plan.

2. **Verify the baseline.** Run `./init.sh` if present, then the test suite. Show the output.
   - Green → note it and continue.
   - Red → **fixing the baseline is this session.** Do not start feature work on a red tree; any
     later failure would be unattributable.
   - No suite → say so explicitly. This session has no verification loop, and everything after
     will be assertion rather than evidence.

3. **Pick exactly one** incomplete feature or task — the one the progress file nominates, unless
   the user says otherwise. Announce it. Do not start a second.

4. **State the finish line** before starting: the command that will prove the work is done.

If any step is unclear — the tree is dirty from another session, the progress file contradicts the
log, the baseline fails for an unrelated reason — **read `references/session-protocol.md`
(next to this file)** for the recovery procedure, and report before proceeding.

## Report

Five lines, then stop and wait for go-ahead:

- **State:** what works today, per the progress file
- **Baseline:** green / red (with the command and result)
- **Picked:** the one feature or task, and why it
- **Finish line:** the command that will prove it done
- **Blocking:** anything that must be resolved first, or "nothing"
