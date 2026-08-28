# Onboarding Moves — making an inherited codebase workable

> **Provenance.** Distilled from the CodeFundation wiki pages `large-codebase-onboarding`,
> `claude-md-memory`, `agent-friendly-architecture` and `context-window-management`
> (upstream: `anthropic-large-codebases`, `claude-code-practice-handbook`,
> `maintainable-agentic-codebase`, `karpathy-skills-claude-md`).

## Contents

1. The thesis
2. The moves, in order of leverage
3. Configuration priority order
4. The CLAUDE.md for an inherited codebase
5. What not to do
6. Ownership

---

## 1. The thesis

Claude Code runs successfully in multi-million-line monorepos and estates spanning dozens of
repositories. What distinguishes the deployments that work is **the harness — the surrounding tools
and configuration — more than the model itself**. So onboarding is a configuration job, not a
reading job.

Two consequences worth stating up front:

- **Don't try to index the codebase.** RAG-style embedding indexes go stale and fail at scale;
  agentic search works better *provided the codebase is set up for it*. Setting it up is what this
  skill does.
- **Scoping beats documenting.** Every paragraph you write costs tokens on every future request.
  Narrowing what the agent looks at costs nothing and helps more.

## 2. The moves, in order of leverage

1. **Initialize/scope in subdirectories, not the repo root.** The single highest-leverage move for
   a monorepo. A session scoped to `services/billing/` sees a tractable project; the same session at
   the root sees noise.
2. **Scope test and lint commands per subdirectory.** Narrow test scope is "the difference between
   autonomy and delegation." A 40-minute root suite means no verification loop at all; a 20-second
   area suite means the agent can self-correct.
3. **`.claudeignore`** for generated code, build output, vendored dependencies, lockfiles, large
   fixtures, snapshots. Cheap, immediate, no maintenance.
4. **Layered CLAUDE.md** — a lean root file, with directory-specific conventions in files beneath it.
5. **A codebase map** where the structure doesn't self-document (format lives with the
   `codebase-cartographer` agent).
6. **LSP plugin for the language** — symbol-level navigation rather than text-based grep matching.
   Often the biggest quality jump per minute of setup in a large repo.
7. **Finish or fence migrations.** Two coexisting patterns make pattern selection unreliable — the
   model will sometimes copy the one you are migrating away from. If you cannot finish the
   migration, name it explicitly in CLAUDE.md and the map.

Stop as soon as the loop is fast and the agent stops guessing. Moves 1–3 solve most projects.

## 3. Configuration priority order

Anthropic's stated order for large codebases, which doubles as the order to add things in:

**CLAUDE.md → hooks → skills → plugins → LSP → MCP servers**

- CLAUDE.md — keep root files lean; layer subdirectory conventions beneath
- Hooks — automate what must always happen, rather than relying on prompts
- Skills — on-demand expertise via progressive disclosure, "to avoid bloating every session"
- Plugins — bundle skills, hooks, and MCP config for org-wide distribution
- LSP — symbol navigation instead of grep
- MCP — internal tools, docs, APIs; add only what is actively used

## 4. The CLAUDE.md for an inherited codebase

Different from a greenfield one. You are documenting **what is true here**, not what should be true:

- **Commands first** — build, test (all), test (one area), lint, format, run. Every one verified by
  running it.
- **Conventions as observed** — "handlers return `Result<T>`; do not throw across the service
  boundary" is useful because it is this codebase's rule. Generic advice is not.
- **Gotchas that cost a session** — the test that must run serially, the service that must be up,
  the directory that looks dead but isn't, the file that regenerates on build.
- **Migrations in flight** — old pattern, new pattern, which files still use the old, which to copy.
- **Nothing the code already says.** Per-line test: *would removing this cause mistakes?* If not,
  cut it. Under 200 lines.

## 5. What not to do

- **Don't summarize the architecture.** A prose summary rots, costs tokens forever, and competes
  with the code as a source of truth. Map paths and commands instead.
- **Don't propose a restructure as part of onboarding.** Note the worst structural problem in one
  line and hand it to the architecture reviewer. Onboarding that turns into a refactor delivers
  neither.
- **Don't write commands you haven't run.** An untested command in CLAUDE.md fails at the moment of
  highest trust.
- **Don't read the codebase exhaustively.** You are building an index. Read excerpts, follow
  imports, use churn to decide what deserves depth.
- **Don't add MCP servers or plugins first.** They are last in the priority order for a reason.

## 6. Ownership

Configuration decays. **Review it every three to six months, and after major model releases**, with
a **named owner** — "bottoms-up adoption generates enthusiasm but fragments without centralization."
Name the owner in the CLAUDE.md you write, or say explicitly that there isn't one.
