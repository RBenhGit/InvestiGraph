# Subagent Authoring

> **Provenance.** Distilled from the CodeFundation wiki pages `subagents`,
> `specialized-agent-roles` and `model-selection-and-effort` (upstream: `claude-docs-subagents`,
> `claude-docs-best-practices`, `wshobson-agents-marketplace`, `obra-superpowers`,
> `claude-code-practice-handbook`). Version-gated details (nesting depth, model IDs) move fast —
> verify against `claude --version` before relying on them.

## Contents

1. When a subagent is the right answer
2. What a subagent starts with
3. Frontmatter
4. Choosing the model
5. Writing the system prompt
6. Tools: grant the minimum
7. Giving it references
8. Output contract
9. Checklist

---

## 1. When a subagent is the right answer

- A side task would flood the main conversation with search results, logs, or file contents you
  will not reference again. The test: **"will I need this output again, or just the conclusion?"**
- You keep spawning the same kind of worker with the same instructions.
- **Fresh context is the point** — review especially: "Claude won't be biased toward code it just
  wrote." Separate windows are also why "one agent can introduce a bug that another agent catches."
- You need a constraint the main session can't have: a reviewer that *cannot* edit.

**Don't** define one when the built-ins cover it: **Explore** (read-only search, thoroughness
levels) and **Plan** (read-only research in plan mode) already exist, and both skip CLAUDE.md and
git status to stay lean. Prefer the main conversation when phases share significant context, need
back-and-forth, or latency matters.

## 2. What a subagent starts with

Nothing but its system prompt, the delegation message, CLAUDE.md + git status (except Explore/Plan),
and any preloaded skills. **No conversation history. No skills you invoked. No auto memory.**

Two consequences for authoring:

- The system prompt must be self-sufficient. "As discussed above" refers to nothing.
- The delegation message carries all task-specific context. If your agent needs an input, say so
  explicitly in its description so callers know to pass it.

## 3. Frontmatter

```yaml
---
name: architecture-reviewer     # kebab-case, matches the filename
description: >                  # required — this is the delegation trigger
  Reviews structure — module boundaries, dependency direction, hidden couplings.
  Use before implementing a design or when a change crosses module lines.
tools: Read, Grep, Glob, Bash   # allowlist; omit to inherit everything
model: opus                     # or sonnet / haiku / inherit — see §4
memory: project                 # persistent cross-session learning, shareable via VCS
---
```

Other fields: `disallowedTools`, `permissionMode`, `skills` (preload full skill content),
`mcpServers` (scope MCP tools to this agent, keeping schemas out of the main window),
`isolation: worktree` (its own git worktree), `maxTurns`, `hooks`.

Precedence: managed > CLI `--agents` > project `.claude/agents/` > user `~/.claude/agents/` >
plugin. **Commit project agents** so the team and every future session get the same behavior.

Invocation: natural language ("use the architecture-reviewer subagent…"), `@agent-<name>` (which
guarantees delegation), or `claude --agent <name>` for a whole session.

## 4. Choosing the model

Assign **per role, not per session**. The community's five-tier scheme:

| Tier | Model | Purpose |
|---|---|---|
| 0 | Long-horizon tier | Autonomous multi-hour work |
| 1 | Opus | Architecture, security, code review |
| 2 | *(unpinned)* | Roles where the user's own model choice should win |
| 3 | Sonnet | Docs, testing, debugging |
| 4 | Haiku | Fast mechanical tasks |

The subtle tier is 2: **leaving `model` unset is a decision, not an omission.** Pinning Sonnet on a
debugging agent downgrades a session the user deliberately started on a stronger model. Pin the
adversarial gates (review, security) to the strongest model available; leave the rest unpinned
unless you have a cost reason.

## 5. Writing the system prompt

- **One task per agent.** An agent that reviews *and* fixes will fix instead of reviewing.
- Open with the role and the hard constraint: *"You are a structural reviewer. You do not edit
  files."*
- Give it a procedure with ordered steps, and the point at which it must stop.
- **Include a refutation step for anything adversarial.** A reviewer asked to find problems will
  find them; unsupported findings push implementers toward defensive code and abstractions the task
  never needed. Require a concrete failing scenario per finding, and require the agent to report
  how many candidates it dropped.
- Say what it must *not* report or do. Negative scope is what keeps a specialist specialized.
- Where fresh-context isolation is the point, say so — it stops the agent from asking for
  conversation history it cannot have.
- `description` deserves the same care as a skill's: it is the delegation trigger, and "use
  proactively" measurably encourages delegation.

## 6. Tools: grant the minimum

- Read-only reviewers: `Read, Grep, Glob, Bash`. **Withholding Edit is the enforcement** — a prompt
  saying "don't edit" is advice; an absent tool is a guarantee.
- Implementers: add `Write, Edit`.
- Anything that writes to a shared artifact (a map, a report) needs `Write`, and should name the
  file it owns.
- Scope MCP servers per agent (`mcpServers`) rather than globally, so their schemas stay out of the
  main window.
- If parallel agents will edit files simultaneously, `isolation: worktree` prevents them colliding —
  at the cost of setup time and disk.

## 7. Giving it references

A subagent cannot see skills you invoked, so knowledge must reach it one of two ways:

1. **Preload with `skills:`** — full content, always paid.
2. **Point at a file and tell it to read it first** — the pattern this kit uses:
   *"Read your standard before you begin: `.claude/standards/<name>.md` (if that path doesn't
   exist, find it with Glob `**/standards/<name>.md`)."*

Prefer (2) for anything long: it survives being copied into another repo, it is auditable as a
plain file, and the fallback Glob keeps it working when the install path differs.

**Keep those files outside `.claude/agents/`.** Agent discovery globs `.claude/agents/*.md`
*including subdirectories*, so a reference file sitting in `.claude/agents/references/` is walked
by the loader on every session. It won't register (no frontmatter, so no `name`), but there is no
reason to hand the loader files that aren't agents — `.claude/standards/` is inert.

## 8. Output contract

The main session sees only a summary, so specify its shape in the prompt: sections, ordering, and
what must be included (`file:line`, evidence, a dropped-candidates count, a verdict). Also specify
what to do when there is nothing to report — *"say so plainly and stop"* — or the agent will invent
findings to justify the run.

Note: subagent output is scanned for instruction-shaped patterns as an injection defense. Don't
design an agent whose output is meant to be executed as instructions by the parent.

## 9. Checklist

- [ ] One task, stated in the first sentence
- [ ] Description says what + when, and is specific enough to trigger reliably
- [ ] Tools are the minimum; constraints are enforced by absence, not by prose
- [ ] Model pinned only where the role justifies it; unpinned is a deliberate choice
- [ ] Prompt is self-sufficient — no reference to conversation the agent cannot see
- [ ] Adversarial roles carry a refutation step and a dropped-candidates count
- [ ] Explicit negative scope ("do not report…", "stop and report when…")
- [ ] Output format specified, including the nothing-to-report case
- [ ] Committed to git
