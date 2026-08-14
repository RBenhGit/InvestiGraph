# Architecture Rules — the standard for structural review

> **Provenance.** Distilled from the CodeFundation wiki page `agent-friendly-architecture`
> (upstream: `maintainable-agentic-codebase`, `fowler-maintainability-sensors`,
> `karpathy-skills-claude-md`, `claude-code-practice-handbook`, `anthropic-large-codebases`).
> If that page changes, update this file — it is the only thing the reviewer reads.

## Contents

1. What you are judging
2. The seven principles, as tests
3. Hidden couplings (the catalog)
4. The three prematures
5. Mechanical enforcement (what to recommend instead of a rule in prose)
6. When the structure can't be changed
7. What is NOT an architecture finding
8. Severity rubric

---

## 1. What you are judging

One question: **can an agent (or a new engineer) find one concern, change it, and verify it
without loading the rest of the system?** Everything below is a way of asking that question
about a specific piece of code.

The premise: agents "must be able to find relevant context, make narrow changes, and
self-verify without loading entire systems into context." Agents cannot compensate for
structural weakness with years of accumulated familiarity the way a long-tenured human can —
they surface it immediately.

## 2. The seven principles, as tests

| Principle | The test to apply |
|---|---|
| **Locality** | Is a complete concern readable in one neighborhood? Domain directory narrows *where to look*; the vertical slice inside it narrows *what to change*. `user/changePassword/` holding command, validator, handler and test together is the target shape. |
| **Small blast radius** | If this change is wrong, what breaks? Change points should sit behind stable interfaces. Agents "cannot self-correct if one small fix triggers broad regressions they cannot detect." |
| **Boundary integrity** | Can a reader infer the real contract from local evidence? Agents reason from partial observation; a weak boundary teaches them the wrong contract. |
| **Navigability** | Does the directory structure act as the map? "Give the agent a map, not a 1,000-page instruction manual." |
| **Narrow rebuild/test scope** | Can this slice be tested without running everything? "Fast, targeted testing is not a convenience — it is the difference between autonomy and delegation." |
| **Ownership-aligned boundaries** | Do module edges match who is responsible for them? Edges that cut across owners generate cross-team coordination for single changes. |
| **Restrained complexity** | Does every layer earn its keep? "Every additional layer... competes with the signal actually determining behavior. For agents, this has a direct token cost." |

## 3. Hidden couplings (the catalog)

These are the findings that matter most, because none of them show up in a diff's line count.
For each: what it is, and how to detect it by reading.

- **Global state** — behavior depends on a mutable value nobody in the call path passed in.
  *Detect:* module-level mutable bindings, singletons, ambient config read deep in the stack.
- **Temporal coupling** — correctness depends on call order that the interface doesn't express.
  *Detect:* `init()` / `configure()` that must precede use; setters that must fire before a getter;
  comments of the form "call this first."
- **Control coupling** — a caller passes a flag that selects the callee's behavior.
  *Detect:* boolean/enum parameters that branch the whole body; `if (mode === ...)` near the top.
- **Semantic coupling** — meaning carried by magic strings, undocumented shapes, or conventions.
  *Detect:* string literals compared across module boundaries; dictionaries/objects passed with no
  declared shape; "the API returns whatever the DB row had."
- **Content coupling** — one module reaches into another's internals.
  *Detect:* imports that bypass the published entry point (deep paths into a sibling slice), tests
  that assert on private helpers.
- **Scattered cross-cutting policy** — one rule (auth, retry, audit, currency rounding) implemented
  in N places. *Detect:* grep the rule's keyword; count call sites; ask where the rule would be
  changed.

## 4. The three prematures

- **Premature abstraction** — an interface introduced before real variation exists. One
  implementation behind an interface is the tell. Rule of three is the usual guide; whether it
  still applies at agent speed is an open question in the wiki, so argue from the concrete case,
  not the rule.
- **Premature generalization** — a false common core: two behaviors merged, then re-separated by
  flags and branches inside the merged unit. The tell is a growing parameter list on a "shared"
  function.
- **Premature optimization** — structure distorted by speculation about cost. Optimize only
  against a measured budget (see `measure-first.md`).

Usable phrasing when you report one, from the most-starred CLAUDE.md in the ecosystem:
*"Minimum code that solves the problem. Nothing speculative"* and *"Would a senior engineer say
this is overcomplicated? If yes, simplify."*

## 5. Mechanical enforcement (what to recommend instead of a rule in prose)

A rule that lives only in markdown is advice; a rule a tool checks is a guarantee.
When you find a structural problem that will recur, prefer recommending a sensor over
recommending vigilance:

- **Complexity / size lint** with self-correcting messages (the message should say what to do,
  not just what's wrong)
- **Dependency rules** — e.g. `dependency-cruiser`-style import restrictions expressing layer and
  slice boundaries. Agents absorb the rule from the failure output and then self-correct against it.
- **Coupling triage** — periodic review of the couplings in §3 rather than one-off cleanups
- **Mutation testing** where test signal is load-bearing (see `test-signal.md`)
- **Pre-commit enforcement beats markdown guidance** — if it must always hold, it belongs in a
  hook or CI, not in CLAUDE.md.

## 6. When the structure can't be changed

For inherited or multi-million-line codebases, navigability can be retrofitted from outside:

- Initialize/scope Claude in **subdirectories, not the repo root**
- **Scope test and lint commands per subdirectory** so verification stays fast
- **`.claudeignore`** for generated files and build artifacts
- Write markdown **codebase maps** where the directory structure doesn't self-document
  (format: `codebase-map-format.md`)
- **Finish migrations or fence the old pattern off.** Two coexisting patterns make the model's
  pattern selection unreliable — it will sometimes copy the one you are migrating away from.
  Partially migrated frameworks are a first-class anti-pattern, not a cosmetic debt.

## 7. What is NOT an architecture finding

Report none of these:

- Naming, formatting, or idiom preferences
- "This could be more general/configurable" — that is the premature-generalization failure, inverted
- A design you would have chosen differently, absent a concrete failure it causes
- Duplication that is currently cheap and local. Tolerated duplication is an accepted trade-off of
  this style; extraction is only better once variation is real
- Missing tests (that is the test-auditor's job), style (the linter's), bugs (the code-reviewer's)

The trade-offs this style knowingly accepts: boundary friction, some duplication, and up-front
verification-infrastructure cost. Do not report an accepted trade-off as a defect.

## 8. Severity rubric

- **Critical** — a boundary violation or hidden coupling that makes a future change unverifiable
  or gives it an unbounded blast radius. Name the future change that breaks.
- **Warning** — restrained-complexity violation, or a coupling that is contained today but will
  spread with the next feature. Name the next feature.
- **Note** — a sensor worth adding (§5), with the exact tool and rule.

Every finding needs: `file:line`, which principle (§2) or coupling (§3) it violates, and the
concrete change that becomes hard because of it. A finding you cannot tie to a future change
is a preference — drop it.
