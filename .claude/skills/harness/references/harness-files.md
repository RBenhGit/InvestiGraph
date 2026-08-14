# Harness Files — formats and reasoning

> **Provenance.** Distilled from the CodeFundation wiki page `long-running-agent-harnesses`
> (upstream: `anthropic-long-running-harnesses`, `claude-docs-best-practices`) with the
> orientation ritual from `efficient-coding-foundation`. File schemas below are this kit's
> convention; the two-phase design, the JSON choice, and the session protocol are sourced.

## Contents

1. The model: shifts, not marathons
2. FEATURES.json
3. PROGRESS.md
4. init.sh
5. The CLAUDE.md block
6. What the harness does not do

---

## 1. The model: shifts, not marathons

Work that outlives one context window behaves like "a software project staffed by engineers working
in shifts, where each new engineer arrives with no memory of the previous shift." Every artifact
here exists so the next shift can start productively without the previous one being present.

The four failure modes of unharnessed long work, and the file that addresses each:

| Failure mode | Addressed by |
|---|---|
| Over-ambition (context exhausted mid-feature, partial work undocumented) | FEATURES.json granularity + one feature per session |
| Premature completion claims | `"passes": false` with a named verification command |
| Insufficient testing | per-feature verification, end-to-end where the feature is user-facing |
| Environmental degradation (messy state left behind) | PROGRESS.md + the clean-state rule + git commits |

## 2. FEATURES.json

**JSON, not Markdown** — deliberately. A structured file is harder to casually overwrite or
"tidy up" mid-session than prose, and the source recommends it for exactly that reason. The
reference implementation used 200+ granular features, each with steps and a `passes` flag.

```json
{
  "project": "<name>",
  "updated": "YYYY-MM-DD",
  "features": [
    {
      "id": "auth-login-happy-path",
      "title": "A registered user can log in with email and password",
      "slice": "auth",
      "steps": [
        "POST /session validates credentials against the stored hash",
        "a session cookie is set with HttpOnly and Secure",
        "the client is redirected to the dashboard"
      ],
      "verify": "npm test -- auth/login && ./scripts/e2e.sh login",
      "passes": false,
      "notes": ""
    }
  ]
}
```

Rules:

- **Granular.** One feature = one observable behavior = one session's work at most. If a feature
  can't be finished in a session, it isn't a feature, it's a milestone — split it.
- **`verify` is mandatory** and must be a runnable command. A feature with no command cannot be
  claimed done, only asserted done.
- **`passes` flips to `true` only after that command has been run and shown.** Never on inspection.
- **Never edit or delete a feature to make progress look better.** Add a note instead. The same
  integrity rule that forbids deleting tests applies here: "it is unacceptable to remove or edit
  tests because this could lead to missing or buggy functionality."
- Keep `notes` for surprises the next shift needs (a workaround, an unexpected dependency).

## 3. PROGRESS.md

Prose, because it carries judgment rather than state a machine reads.

```markdown
# Progress — <project>

**Updated:** YYYY-MM-DD (commit <sha>)

## Where things stand
Two or three sentences. What works end to end today.

## Last completed
<feature id> — what was done, the verification that passed, the commit.

## In flight
Nothing, or: <feature id>, exactly what is half-done and what remains. If this section is
non-empty at the end of a session, the session did not finish clean — say why.

## Known problems
Bugs, flaky tests, environment quirks. Each with: seen where, impact, and whether it blocks.

## Next up
<feature id> and the one thing its implementer should know before starting.
```

## 4. init.sh

One script that takes a clean checkout to a running, verifiable system: install → build →
migrate/seed → run (and, where it applies, a smoke check). It exists so that step 2 of every
session ("verify the baseline") is one command rather than an archaeology exercise.

Keep it idempotent, keep it fast, and make it fail loudly with a message that says what to fix.
If setup genuinely requires human action (a credential, a local service), have the script detect
the missing piece and print exactly what to do.

## 5. The CLAUDE.md block

The ritual only works if it is in the always-loaded layer. Short, because it costs tokens on
every request:

```markdown
## Multi-session protocol
1. Orient: read the last 10 commits, PROGRESS.md, and FEATURES.json before changing anything.
2. Verify the baseline with ./init.sh and the test suite. If it's red, fixing that is the session.
3. Take ONE feature with "passes": false. Do not start a second.
4. Finish clean: verification output shown, `passes` flipped, PROGRESS.md updated, commit with a
   descriptive message, tree mergeable.
```

## 6. What the harness does not do

- It is not a substitute for a spec. FEATURES.json records *what must work*; SPEC.md records
  *what we decided and why*. Derive the former from the latter rather than maintaining two plans.
- It does not decide priority. A human orders the feature list.
- It does not survive dishonesty. Every mechanism here assumes `passes` is only flipped on evidence;
  nothing in the file format can enforce that. The Stop-hook test gate is what makes it mechanical.
- First-party tooling now overlaps parts of this (`/goal` keeps a session working until a condition
  holds; `ralph-loop` re-runs a task until completion; `remember` compresses sessions into daily
  logs). Use them if they fit — the files above are the portable, inspectable version, and they
  work in any session including headless CI.
