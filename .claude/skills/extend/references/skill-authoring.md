# Skill Authoring

> **Provenance.** Distilled from the CodeFundation wiki page `agent-skills`
> (upstream: `anthropic-skill-authoring`, `claude-docs-skills`, `anthropic-large-codebases`,
> `official-marketplace-2026-08`).

## Contents

1. When a skill is the right answer
2. Frontmatter
3. Writing the description (the trigger)
4. Writing the body
5. Progressive disclosure
6. Degrees of freedom
7. Feedback loops inside a skill
8. Evaluation-driven authoring
9. Checklist

---

## 1. When a skill is the right answer

- You have pasted the same instructions, checklist, or procedure into chat a third time
- A CLAUDE.md section "has grown into a procedure rather than a fact"
- Knowledge that is needed *sometimes* and is expensive to carry always

Skills and custom commands are the same mechanism now — both create `/name`; skills add supporting
files, invocation control, and automatic loading.

## 2. Frontmatter

```yaml
---
name: slice                      # matches the directory name; becomes /slice
description: >                   # the trigger signal — see §3
  Decompose a feature into vertical slices and 2-5 minute tasks with file paths
  and verification steps
disable-model-invocation: true   # user-only. Zero context until invoked. Use for
                                 # side-effect workflows (/deploy, /commit) and for
                                 # anything the model shouldn't start on its own
argument-hint: "[feature or SPEC.md path]"
---
```

Other fields worth knowing: `user-invocable: false` (background knowledge the model may load but
the user never types), `allowed-tools` (pre-approved for the invoking turn), `context: fork` plus
`agent:` (run the skill in a subagent), `paths:` (auto-load only for matching files).

Locations: personal `~/.claude/skills/<name>/SKILL.md`, project `.claude/skills/` — **commit
project skills; cloud sessions only see repo-committed skills** — or a plugin (namespaced
`/plugin:name`). Nested discovery works in monorepos.

Dynamic context: `` !`command` `` runs before the model sees the file, so instructions arrive with
live data inlined (e.g. `` !`git diff HEAD` ``). Use it to save a turn, not to dump output.

## 3. Writing the description (the trigger)

The description is how the model decides to load the skill, and how the user finds it. It is the
single highest-leverage line in the file.

- **Third person, specific, with the terms a user would actually type.**
- Say **what** it does *and* **when** to use it.
- Good: *"Extract text and tables from PDF files. Use when working with PDF files or when the user
  mentions PDFs, forms, or document extraction."*
- Bad: *"Helps with documents."*
- Descriptions compete: when twenty skills could match, the specific one wins. Vague descriptions
  crowd the listing budget without ever firing.

## 4. Writing the body

- **Assume the model is already very smart.** Add only the context it does not have: your
  conventions, your paths, your decisions. Delete anything a competent engineer would already do.
- **Challenge every paragraph's token cost.** Invoked skill content stays in context for the rest of
  the session — every line is a recurring cost, not a one-off.
- Imperative and concrete. Name files, commands, and expected outputs.
- **Consistent terminology.** One name per concept, throughout.
- **No time-sensitive information** (version numbers, "currently", prices) unless the skill's whole
  job is to track it — it rots and then misleads.
- **No magic numbers** without their reason.
- Say what the skill should *not* do, and where it should stop and report.

## 5. Progressive disclosure

- `SKILL.md` under 500 lines, structured as a table of contents to what follows.
- Supporting files **one level deep** (`references/`, `scripts/`, `assets/`).
- Any reference file over ~100 lines gets its own contents list at the top.
- **Load conditionally**: "if X is unclear, read `references/y.md`" beats loading everything up
  front. The happy path should not pay for the recovery path.
- **Scripts are executed, not read** — only their output costs tokens. Prefer a script over prose
  when the operation is deterministic. Scripts should solve, not defer ("here's how you might…").

## 6. Degrees of freedom

Match the freedom you grant to how fragile the task is:

- **High freedom** (heuristics, judgment, "prefer X over Y") for context-dependent work: review,
  design, decomposition.
- **Low freedom** (exact commands, "do not modify this command") for fragile operations:
  migrations, releases, destructive or irreversible steps.

Mismatches are the common authoring bug: a rigid script for a judgment task produces nonsense, and
loose heuristics for a migration produce an outage.

## 7. Feedback loops inside a skill

- **Validator loop**: run validator → fix errors → repeat. Reported to "greatly improve output
  quality," and it is the cheapest quality mechanism available to a skill.
- **Plan-validate-execute**: for risky or batch operations, have the skill write a machine-checkable
  plan file, validate it, then execute. Verbose, specific error messages matter — they are what the
  model self-corrects against.

## 8. Evaluation-driven authoring

Write the evals **before** the documentation. The sequence:

1. Collect 3+ real examples of the task.
2. **Baseline without the skill.** Record exactly what goes wrong — those failures are the only
   thing the skill should address.
3. Write the minimum instructions that close the observed gaps.
4. Re-run. Iterate: an author instance writes, a **fresh** instance tests (a Claude A / Claude B
   loop — the author knows too much to be a fair tester).
5. Include a negative case: a task where the skill should *not* fire.

Skill quality is invisible from the outside — a skill that loads and produces plausible output can
still be worse than no skill. That is what the with/without baseline is for. The `skill-creator`
plugin automates this, including blind A/B version comparison and variance analysis.

## 9. Checklist

- [ ] Description is third person, specific, and states what + when
- [ ] Body under 500 lines and structured as a table of contents
- [ ] Supporting files one level deep; long references have their own contents list
- [ ] Conditional loading for anything not needed on the happy path
- [ ] Consistent terminology; no time-sensitive facts; no unexplained numbers
- [ ] Degrees of freedom match the task's fragility
- [ ] Scripts solve rather than defer
- [ ] ≥3 evals, including one negative case, with a recorded without-the-skill baseline
- [ ] Committed to git
