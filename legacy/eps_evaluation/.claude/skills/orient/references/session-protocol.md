# Session Protocol — orientation, recovery, and finishing clean

> **Provenance.** Distilled from the CodeFundation wiki pages `long-running-agent-harnesses`,
> `verification-loops` and `context-window-management` (upstream:
> `anthropic-long-running-harnesses`, `claude-docs-best-practices`,
> `claude-code-practice-handbook`, `obra-superpowers`). Read this only when orientation hits a
> problem — the happy path is in SKILL.md.

## Contents

1. Recovery: the tree is dirty
2. Recovery: the baseline is red
3. Recovery: the progress file disagrees with the code
4. Recovery: no verification exists
5. Finishing clean (the other half of the ritual)
6. Mid-session context hygiene

---

## 1. Recovery: the tree is dirty

Uncommitted changes from an earlier session are unattributed work. Do not build on them and do not
discard them.

1. `git status --short` and `git diff` — read what is actually there.
2. Classify: (a) finished work that was never committed, (b) an abandoned partial attempt,
   (c) local environment noise (config, editor files).
3. Report the classification and **ask** before acting. Committing someone's half-finished work
   under your own message destroys the audit trail; deleting it destroys the work.
4. Only once it's resolved: re-run the baseline and continue.

The exception is (c): environment noise that is clearly untracked local config can be left alone,
but say so.

## 2. Recovery: the baseline is red

A red baseline means **this session's work is fixing the baseline**. That is not a detour; it is
the highest-value thing available, because until it's green nothing else can be verified.

1. Capture the failure exactly (command, output, exit code).
2. Establish when it broke: `git log --oneline -20`, then bisect by checking out a known-good
   commit and re-running. `git bisect` if the range is wide.
3. Fix the root cause. Never skip, delete, or weaken the failing test to get green — that converts
   a known problem into an unknown one.
4. If the break is environmental (missing dependency, stale build, changed service), fix `init.sh`
   so the next session doesn't repeat the archaeology.
5. Commit the fix on its own, then decide with the user whether to continue into feature work.

If the failure predates every commit you can reach, or belongs to someone else's in-flight branch,
stop and report rather than guessing.

## 3. Recovery: the progress file disagrees with the code

Trust the code and the tests, in that order; the progress file is a claim, the suite is evidence.

1. Re-run the verification command for the disputed feature.
2. Passes → the file is stale. Update it, and note the correction in the commit message.
3. Fails → the feature was marked done without evidence. Flip it back to `"passes": false`, record
   the failure in the progress file's **Known problems**, and treat it as the session's candidate
   work. Say plainly that a completion claim was unsupported — silently re-doing it hides a
   process failure that will recur.

## 4. Recovery: no verification exists

Without a runnable check "you become the verification loop: every mistake waits for you to notice
it." Say so explicitly, and propose the cheapest thing that closes it:

- One end-to-end smoke check for the main path (a script, a request, a page load)
- A single test for the area about to change
- A build/typecheck command, if there is genuinely nothing else

Build that first, get it passing, commit it, then start the actual work. One command that fails
when the product is broken is worth more than a plan to add tests later.

## 5. Finishing clean (the other half of the ritual)

Every session must end mergeable: no major bugs, orderly, documented. Before you stop:

1. **Verification output shown** for the work done — not a claim about it.
2. **State updated**: flip `passes` only on evidence; update PROGRESS.md's *Last completed*,
   *In flight* (empty if you finished), *Known problems*, and *Next up*.
3. **Commit** with a descriptive message. Git is both the memory and the undo.
4. **Leave nothing half-applied.** If you must stop mid-feature, revert to the last green state or
   leave the tree building and passing, and write exactly what remains in *In flight*.
5. **Hand over what won't be obvious**: a surprise, a workaround, a wrong assumption you corrected.
   The next shift has no memory of this one.

## 6. Mid-session context hygiene

- Delegate anything high-volume — test runs, log digs, wide searches — to a subagent. The test is
  **"will I need this output again, or just the conclusion?"**
- After two failed corrections on the same issue, stop correcting. Rewind to before the failure and
  re-prompt with what you learned; a clean session with a better prompt almost always beats a long
  session carrying accumulated corrections.
- Watch the fill. Community practice keeps sessions under ~40% of the window, ideally below 30% for
  work that needs the model sharp. (Unofficial — no vendor figure exists — but it's the only
  published threshold.)
- New unrelated task → new session. Closely related follow-up (documenting what you just built) →
  reuse the context.
