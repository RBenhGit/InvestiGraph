# Codebase Map Format

> **Provenance.** Distilled from the CodeFundation wiki pages `large-codebase-onboarding` and
> `agent-friendly-architecture` (upstream: `anthropic-large-codebases`,
> `maintainable-agentic-codebase`, `claude-code-practice-handbook`).
> Anthropic's guidance names the artifact — "markdown codebase maps" for codebases whose directory
> structure doesn't self-document — without specifying a format. The wiki carries that as an open
> question. **This file is our answer**; treat it as a convention, not as sourced fact.

## Contents

1. Design constraints
2. The template
3. How to gather each section
4. Keeping it true

---

## 1. Design constraints

A map is read at the start of a session, when the reader knows nothing. It must therefore be:

- **A map, not a manual.** "Give the agent a map, not a 1,000-page instruction manual." If the
  directory structure already says it, don't repeat it.
- **Navigational, not explanatory.** Its job is to answer *where do I look* and *what will break*,
  then get out of the way. Explanations belong in the code.
- **Short enough to be read every time.** One screen per area. If an area needs more, it needs
  its own map file, one level down.
- **Falsifiable.** Every claim should be checkable against the repo by grep or by running a
  command — so the next session can detect drift.
- **Path-accurate.** Every path in it must exist. A wrong path costs more than a missing section.

Write it to `docs/codebase-map.md` (or the project's docs convention) and link it from CLAUDE.md
with one line. In a monorepo, write one map per top-level area, next to that area — not one root
map for everything.

## 2. The template

```markdown
# Codebase Map — <repo or area>

**Last verified:** YYYY-MM-DD against commit <sha>

## What this is
One paragraph: what the system does, for whom, and the one thing a newcomer gets wrong about it.

## Orientation
| I need to... | Start at |
|---|---|
| add an API endpoint | `src/api/routes/` — then the slice under `src/domains/<domain>/` |
| change how X is stored | `src/domains/x/repository.ts` |
| understand auth | `src/platform/auth/README.md` |

## Areas
### <area name> — `path/`
- **Owns:** the concern, in one sentence
- **Entry points:** the files other areas are allowed to import
- **Depends on:** other areas, and the direction the dependency is allowed to run
- **Tests:** `<command that runs only this area's tests>` (~<duration>)
- **Watch out for:** the one non-obvious thing (a hidden coupling, a legacy pattern, a generated file)

## Boundaries and rules
- Dependency direction: <e.g. domains → platform → shared; never the reverse>
- Enforced by: <tool/config, or "nothing — convention only">
- Anything that reaches across these lines is a bug; see `<lint config>`.

## Build, test, run
| Task | Command | Notes |
|---|---|---|
| install | | |
| build | | |
| test (all) | | duration — if it's slow, say so |
| test (one area) | | this is the one that matters for the loop |
| lint / format | | |
| run locally | | prerequisites: services, env vars, seeds |

## Generated / do not edit
Paths that are generated, vendored, or otherwise not hand-edited (and what regenerates them).
Candidates for `.claudeignore`.

## Migrations in flight
Any place where two patterns coexist: the old pattern, the new one, which files still use the old,
and which one to copy. **This section is load-bearing** — two coexisting patterns make pattern
selection unreliable, so an agent will otherwise sometimes copy the pattern you are leaving.

## Known sharp edges
Non-obvious failure modes: flaky tests and why, slow paths, environment quirks, "this looks unused
but isn't."

## Unknowns
What this map does not cover, and what you'd have to read to find out. Never guess to fill a gap.
```

## 3. How to gather each section

Work outside-in and cheaply. Prefer commands whose output you can cite.

1. **Shape first** — top-level directories, then one level down. `git ls-files | head -n 200`,
   directory listings, and the package/build manifests. Read manifests before source: they name the
   entry points, scripts, and dependency edges for free.
2. **Entry points** — build config, `main`/`bin`/`exports` fields, route registries, DI containers.
3. **Ownership and churn** — `git log --format='' --name-only --since=6.months | sort | uniq -c |
   sort -rn | head -40` shows where the work actually happens. Map the hot areas in detail and the
   cold ones in one line each.
4. **Tests** — find the runner config, then determine *how to run one area's tests*. This is the
   single most valuable line in the map: narrow test scope is "the difference between autonomy and
   delegation."
5. **Boundaries** — look for an existing dependency-rule config (`dependency-cruiser`, ESLint
   import rules, module boundaries in build config). If none exists, state the convention you
   observed and label it "convention only, unenforced."
6. **Migrations** — grep for two names for the same thing (old/new client, v1/v2 handlers,
   deprecated helpers), and check for a migration doc or a tracking issue.
7. **Verify before writing.** Every path: confirm it exists. Every command: run it, or mark it
   `unverified` explicitly.

Read excerpts, not whole files. You are building an index, not a summary.

## 4. Keeping it true

- Stamp the map with the commit it was verified against (§2 header).
- On re-runs, **update in place** — diff the map against reality, fix what drifted, and report what
  changed. Do not rewrite a map that is still accurate.
- Prune aggressively. A map that grows into a manual stops being read, and an unread map rots
  silently.
- If the structure itself is the problem, say so once in **Known sharp edges** and stop. Restructure
  proposals belong to the architecture reviewer, not the map.
