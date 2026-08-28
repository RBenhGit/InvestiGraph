# Claude Code Starter Kit

A minimal, opinionated foundation for starting a new project with [Claude Code](https://code.claude.com): a CLAUDE.md built on **simplicity** and **modularity**, deterministic quality gates as hooks, three specialized agents, and two workflow skills.

Compiled from Anthropic's official guidance and field-tested community practice — the full research wiki with sources and rationale lives in [RBenhGit/CodeFundation](https://github.com/RBenhGit/CodeFundation) (see `wiki/topics/efficient-coding-foundation.md` for the playbook this kit implements).

## Contents

```
├── CLAUDE.md                        # Project memory template ({{PLACEHOLDERS}} to fill)
└── .claude/
    ├── settings.json                # Hook wiring + minimal allow/deny permission rules
    ├── hooks/
    │   ├── protect-files.sh         # PreToolUse: blocks edits to .env, lockfiles, .git/
    │   ├── post-edit.sh             # PostToolUse: format + lint each edited file
    │   └── stop-test-gate.sh        # Stop: refuses to finish while tests fail
    ├── agents/
    │   ├── code-reviewer.md         # Read-only two-stage diff review, fresh context
    │   ├── test-writer.md           # Failing-tests-first; never touches implementation
    │   └── debugger.md              # Root cause only — never suppresses symptoms
    └── skills/
        ├── spec/SKILL.md            # /spec — interview → SPEC.md → implement fresh
        └── new-module/SKILL.md      # /new-module — scaffold a vertical slice
```

## Get started

1. Click **Use this template** → create your project repo (or copy `CLAUDE.md` and `.claude/` into an existing one).
2. Fill every `{{PLACEHOLDER}}` in `CLAUDE.md` — or run `/init` first and merge; keep the result under 200 lines.
3. Open `.claude/hooks/post-edit.sh` and `.claude/hooks/stop-test-gate.sh` and set `FORMAT_CMD` / `LINT_CMD` / `TEST_CMD` for your stack. **They are no-ops until you do** — the kit never breaks an unconfigured repo. Keep the scripts executable (`chmod +x .claude/hooks/*.sh`; requires `jq`).
4. Install the code-intelligence plugin for your language (`/plugin` → e.g. `typescript-lsp`, `pyright-lsp`, `rust-analyzer-lsp`) and, if you review PRs, `code-review` or `pr-review-toolkit`. Worth adding once the project is real: `hookify` (turn a correction you keep repeating into a hook), `session-report` (see which skills and agents actually cost you context), `claude-md-management` (audit and prune CLAUDE.md).
5. Commit all of it. The foundation only works if every session and teammate gets it.
6. **Start Claude interactively once in the repo and accept the trust dialog.** Until you do, the `permissions.allow` entries in `settings.json` are ignored and you'll be prompted for even `git status`. Headless (`claude -p`) runs in an untrusted directory silently skip them.

The kit itself uses only long-standing features and works on any current Claude Code. Two things mentioned below are newer: `/code-review` runs as a background subagent from v2.1.218, and `/ultrareview` needs a plan with cloud review. If something in the kit misbehaves, `--safe-mode` starts with all customizations disabled and `/doctor` diagnoses setup problems.

## The principles

The CLAUDE.md template ships four, in the order Claude reads them:

0. **Think before coding** — state assumptions rather than guessing; surface ambiguity instead of silently picking; push back when a simpler approach exists; stop and say so when confused.
1. **Simplicity** — a simple concept is less complicated to debug. No abstraction until variation is real; no speculative flags, layers, or config.
2. **Modularity** — clear separation makes issues locatable. Domain directories with vertical slices, explicit interfaces, no reaching into internals; a change touches one slice and its tests.
3. **Surgical changes** — touch only what the task requires; don't refactor unbroken adjacent code; match existing style; only remove dead code your own change created.

1 and 2 are the architectural bet. 0 and 3 exist because the two most expensive agent failures aren't bad code — they're confidently building the wrong thing, and quietly changing more than you asked.

## Daily loop (short version)

Large feature → `/spec` → fresh session implements SPEC.md.
Any non-trivial change → plan mode first.
Risky or multi-session work → worktree on a new branch, suite green *before* the first edit.
Bugs → `debugger` agent (or a failing test first).
Before commit → `code-reviewer` agent or `/code-review` (runs as a background subagent, so it doesn't block you). For a high-stakes diff, escalate to `/ultrareview`.
The Stop gate keeps a session honest when you walk away.

## How the reviewer works

`code-reviewer` runs in two ordered stages, because the two questions are not interchangeable:

1. **Does this do what was asked?** — missing requirements, contradicted behavior, out-of-scope edits. If anything turns up here, it reports and **stops**: there's no point polishing code that solves the wrong problem.
2. **Is the code sound?** — logic errors, edge cases, simplicity/modularity violations, weak tests, secrets.

Before reporting, it tries to *refute* each finding and drops any it can't tie to a concrete failure, then tells you how many it dropped. A reviewer asked to find problems will always find some; unchallenged findings push you toward defensive code and abstractions you never needed.

It's the one agent pinned to `model: opus` — it's the gate everything else rests on. `test-writer` and `debugger` are deliberately left unpinned so they inherit your session's model; pinning them to something cheaper would downgrade a session you deliberately started on a stronger model.

## Keep it healthy

The setup layer decays — the model changes, the codebase grows, the rules stop matching reality. Two habits and one calendar item:

**When to add config** (don't add it preemptively):

| Trigger | Goes in |
|---|---|
| Claude makes the same mistake twice | CLAUDE.md |
| You type the same prompt a third time | a skill |
| Something must happen *every* time | a hook |
| A second repo needs the same setup | a plugin |

**Review every 3–6 months, and after major model releases**, with one named owner. Bottom-up adoption fragments without someone responsible for it. Run `/usage` and `session-report` to find what's expensive, `/doctor` to propose CLAUDE.md trims, `skill-creator` to benchmark a skill against not having it.

**Two habits that belong to you, not to CLAUDE.md:**
- **Rewind rather than correct.** Double-Esc back to before the failure and re-prompt with what you learned. Corrections stack up in context; rewinding leaves nothing behind.
- **Watch the fill.** Community practice keeps sessions under ~40% of the context window, ideally below 30% for work that needs Claude at its sharpest. Unofficial — Anthropic publishes no figure — but it's the only published threshold and it matches the shape of the problem.

## Deliberately NOT included

- **Explorer/planner agents** — Claude Code's built-in `Explore` and `Plan` agents already do this; duplicating them adds noise.
- **A generic review skill** — the bundled `/code-review` exists; the `code-reviewer` agent here adds only the project-specific rules (simplicity/modularity findings).
- **Dozens of role agents** — start minimal; add an agent only when you keep spawning the same worker with the same instructions.
- **MCP servers** — connect per need (`claude mcp add`); prefer CLIs (`gh`) where they exist.
- **Auto mode** — the classifier that handles routine permission prompts is a per-account choice, not a template default. It removes friction; the Stop gate and the PreToolUse guard here are what provide guarantees. `deny` rules beat `allow` rules unconditionally, and both sit *below* auto mode.
- **A whole methodology** — if you want a full opinionated workflow rather than a foundation to build on, `superpowers` is in the official marketplace (mandatory 7-phase pipeline, subagent-per-task, enforced TDD). It's an alternative to this kit, not an addition to it.
