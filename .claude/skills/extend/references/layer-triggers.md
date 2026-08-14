# Which Layer? — triggers, costs, and the decision procedure

> **Provenance.** Distilled from the CodeFundation wiki pages `efficient-coding-foundation`
> (the trigger rule), `self-improving-harness`, `context-window-management`, `claude-md-memory`,
> `hooks`, `plugins` and `agent-skills` (upstream: `claude-docs-features-overview`,
> `anthropic-large-codebases`, `official-marketplace-2026-08`, `claude-docs-memory`,
> `claude-docs-hooks`, `karpathy-skills-claude-md`).

## Contents

1. The trigger rule
2. What each layer costs
3. The decision procedure
4. CLAUDE.md — facts
5. Hooks — guarantees
6. Plugins — distribution
7. Removing things

---

## 1. The trigger rule

| Trigger | Layer |
|---|---|
| Claude makes the same mistake **twice** | CLAUDE.md |
| You type the same prompt a **third** time | a skill |
| Something must happen **every** time | a hook |
| A **second repo** needs the same setup | a plugin |
| You keep spawning the same worker with the same instructions | a subagent |
| A side task floods the main window with output you won't reference again | a subagent |

The counts are the point. Configuration added on a single occurrence is speculative — the same
failure as premature abstraction, except it is charged to every future session.

## 2. What each layer costs

| Layer | Context cost | When it is paid |
|---|---|---|
| **CLAUDE.md** | Full file | Every request, forever |
| **Skill** | Description only (~1–2 lines) until invoked; full body once invoked, for the rest of the session | On match / invocation |
| **Skill with `disable-model-invocation: true`** | Zero until the user types `/name` | Only on explicit use |
| **Subagent** | Its own window; only its summary (typically 1–2k tokens) returns | On delegation |
| **Hook** | Zero unless it returns output | On the matched event |
| **MCP server** | Tool schemas, deferred until used | On use |

This table is the whole argument for progressive disclosure: **the context window is a public
good**. A fact belongs in CLAUDE.md only if it must be true on every request; anything procedural
is cheaper as a skill. Anthropic's large-codebase guidance places skills third in the priority
order specifically "to avoid bloating every session with unnecessary context."

## 3. The decision procedure

Ask in this order; take the first yes.

1. **Must it happen deterministically, every time, without the model choosing?** → **hook**.
   Formatting, protected paths, a test gate at Stop. Anything you would be upset to find skipped.
2. **Is it a fact that changes how *every* task is done here?** → **CLAUDE.md**, in the smallest
   number of lines. Build commands, the two principles, verification policy, a repo-wide gotcha.
3. **Is it a procedure with steps, run only sometimes?** → **skill**. Release, scaffold, spec
   interview, decompose, audit.
4. **Is it a role with its own standards, its own tools, and output you want isolated?** →
   **subagent**. Especially where fresh context is the point: a reviewer shouldn't be biased toward
   code it just wrote.
5. **Is it proven, and needed in a second repo?** → **plugin**.
6. **None of the above** → do nothing yet. Write it down and wait for the second occurrence.

Two refinements worth knowing:

- **Skill vs subagent**: skills run *in* the main context (they see the conversation); subagents run
  *outside* it and return a summary. Choose by whether the work needs the conversation or would
  pollute it. Prefer the main conversation when phases share significant context, need
  back-and-forth, or latency matters.
- **Skill vs hook**: a skill is advice the model may adapt; a hook is a guarantee. If "usually" is
  acceptable, use a skill.

## 4. CLAUDE.md — facts

- Under 200 lines. Per-line test: **would removing this cause Claude to make mistakes?** If not, cut.
- Layer it: lean root file, directory-specific conventions in files beneath.
- State rules as verifiable conditions, not aspirations.
- Instructions that keep being ignored are usually competing with too much other text — the fix is
  removing lines, not adding emphasis.
- `/doctor` can propose trims; `claude-md-management` audits quality and captures session learnings.

## 5. Hooks — guarantees

- Lifecycle events: PreToolUse (block before it happens), PostToolUse (format/lint after an edit),
  Stop (refuse to finish while a check fails), SubagentStart/Stop.
- **Fail safe.** A hook that errors on an unconfigured project must be a no-op, not a blocker.
  Templates in this repo's `starter-kit/` are deliberately no-ops until you set their commands.
- A hook is executable code that runs on every matched tool call — review it like production code,
  and remember that installed/plugin hooks are code you did not write.
- A Stop gate is overridden after 8 consecutive blocks; it is a strong gate, not an infinite one.
- `hookify` converts an observed repeated failure into a hook without hand-writing matchers.

## 6. Plugins — distribution

- Package **skills, agents, hooks, and MCP config** into one installable unit; the mechanism for
  giving a second repo or a whole org the same setup.
- Package only what has already proved out in one repo. A plugin is a distribution decision, not a
  design one.
- Check the official marketplace before authoring: an LSP for the language, a review bundle, and
  the maintenance tools (`hookify`, `session-report`, `claude-md-management`, `skill-creator`)
  already exist.

## 7. Removing things

Adding is the easy half. The setup layer decays as the model, the codebase, and the team change.

- **Measure instead of guessing**: `/usage` breaks consumption down by skill, subagent, plugin, and
  MCP server; the `session-report` plugin does the same from local transcripts, including the most
  expensive prompts.
- **Benchmark rather than assume**: `skill-creator` runs with/without comparisons and blind A/B
  version tests. A skill that has never been compared against not having it is unproven.
- **Schedule the review** — every three to six months and after major model releases, with a named
  owner.
- Delete an extension when the mistake it prevented no longer happens, when the model improved past
  needing it, or when nobody can point to a session it helped.
