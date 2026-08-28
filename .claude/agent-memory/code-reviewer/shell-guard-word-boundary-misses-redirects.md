---
name: shell-guard-word-boundary-misses-redirects
description: .claude/hooks/protect-bash.sh's word-boundary regex omits redirect operators, so `echo x >.env` (no space) slips past the guard that `echo x > .env` triggers
metadata:
  type: project
---

`.claude/hooks/protect-bash.sh` (added Phase 9, 2026-08-28) blocks shell commands that write to a
protected path. Its `mentions()` helper requires the protected name to be preceded by one of
`[[:space:]"'` + backtick + `/=(;&|]`. Redirect operators `>` and `<` are **not** in that class,
so the extremely common no-space form slips through.

Confirmed by reproduction (2026-08-28, staged Phase 9 diff, feeding JSON events straight into the
hook):

| command | hook exit |
|---|---|
| `echo x > .env` | 2 (blocked) |
| `echo x >.env` | 0 (allowed) |
| `echo x >>.env` | 0 (allowed) |

The header comment of the hook names `echo x > .env` as the exact gap it exists to close, so the
guard fails in the scenario it was written for. Fix is one character class:
add `>` (and `<`) to the leading set in the `grep -qE` on line 37.

**Why:** the boundary class was written for word-separated arguments and never exercised against
the operator-adjacent form; the WRITE_OPS detection itself is fine — only the name-matching step
misses.

**How to apply:** when reviewing any change to `.claude/hooks/protect-bash.sh`,
`protected-paths.sh`, or any future heuristic shell guard, do not accept "confirmed live" on a
single spaced example — probe the no-space (`>file`), append (`>>file`), and quoted
(`>"file"`) variants too. Related: [[unbounded-user-fed-registry]] is the same failure mode one
layer up — a guard whose input space is wider than the examples it was tested against.
