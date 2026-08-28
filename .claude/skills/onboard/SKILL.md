---
name: onboard
description: Make an inherited or large codebase workable for agents — scoped CLAUDE.md files, per-directory test and lint commands, .claudeignore, and a codebase map, in that order of leverage
disable-model-invocation: true
argument-hint: "[repo root, or the subdirectory to scope to]"
---

Make this codebase workable: $ARGUMENTS

**Read `references/onboarding-moves.md` (next to this file) first.** It carries the ordered moves,
Anthropic's configuration priority order, and the reasoning for why scoping beats documenting.

This is for a codebase you did not design and cannot restructure. If you control the structure,
fix the structure instead — ask the architecture-reviewer what to change.

## Procedure

Work the moves in the reference's order and **stop when the loop is fast enough**; a project does
not need all of them.

1. **Survey** — size, languages, top-level layout, build/test tooling, and where the work actually
   happens (`git log` churn). Read manifests before source. Do not read broadly; you are locating,
   not learning.

2. **Scope** — decide the working directory. In a monorepo, scope to a subdirectory rather than the
   root; that single move is the highest-leverage one available.

3. **Find the fast check** — the command that runs *only* the relevant area's tests, and its
   duration. Everything downstream depends on this existing. If it doesn't, say so — creating it is
   the most valuable work available here.

4. **Write the CLAUDE.md** for that scope: commands (build, test-all, test-one, lint, run), the
   conventions you observed *in this code* (not general best practice), and the gotchas that will
   otherwise cost a session. Under 200 lines, layered per directory rather than one root file.

5. **Add `.claudeignore`** for generated files, build artifacts, vendored code, and fixtures.

6. **Map it** — if the directory structure doesn't self-document, delegate to the
   `codebase-cartographer` agent (it owns the format) or, if unavailable, follow its standard.

7. **Record migrations in flight** — anywhere two patterns coexist, name the old, the new, and
   which to copy. This is the highest-value paragraph you will write: two live patterns make the
   model's pattern selection unreliable.

## Verify before you claim

Run every command you wrote into CLAUDE.md and show the output. An onboarding artifact full of
untested commands is worse than none — it fails on the next session's first move, in the place
they trust most.

## Output

- What you scoped to, and why
- The fast check and its duration
- Files created or updated
- Command verification output
- **Unknowns** — what you could not determine and what would settle it
- The single change that would most improve this codebase for agents (one line, no plan)
