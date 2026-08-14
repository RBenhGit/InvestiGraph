---
name: extend
description: Add a capability to this project's Claude setup — decide which layer it belongs in (CLAUDE.md, skill, subagent, hook, or plugin), author it there, and prove it earns its context cost
disable-model-invocation: true
argument-hint: "[what keeps going wrong, or the capability you want]"
---

Extend the setup for: $ARGUMENTS

Most requests to "add a skill" are really requests to fix a recurring failure, and the right layer
is often not the one the user named. Decide the layer first.

## 1. Decide the layer

**Read `references/layer-triggers.md` (next to this file).** It carries the trigger rule, what each
layer costs in context, and the decision procedure.

Then state your recommendation in one line — *"this is a hook, not a skill, because it must happen
every time"* — with the trigger that justifies it. If the user asked for a different layer, say why
you disagree, then follow their call if they hold to it.

**Do not add anything on a first occurrence.** One mistake is not a pattern; premature
configuration is the same failure as premature abstraction, and it is paid on every future request.

## 2. Author it

Read the reference for the layer you chose:

| Layer | Read | Then |
|---|---|---|
| **Skill** | `references/skill-authoring.md` | write `.claude/skills/<name>/SKILL.md` |
| **Subagent** | `references/agent-authoring.md` | write `.claude/agents/<name>.md` |
| **CLAUDE.md fact** | `references/layer-triggers.md` §4 | add the smallest line that prevents the mistake |
| **Hook** | `references/layer-triggers.md` §5 | write the script + `settings.json` wiring; must fail safe |
| **Plugin** | `references/layer-triggers.md` §6 | package existing, proven pieces — never author new ones straight into a plugin |

Write the minimum that closes the observed gap. Assume the model is already capable: add only the
context it does not have.

## 3. Prove it

An extension that loads and produces plausible output can still be worse than not having it. Before
declaring it done:

1. **Baseline** — run a real example of the task *without* the new extension. Record what went wrong.
2. **With it** — run the same example with it. Record the difference.
3. **Three cases minimum**, including one where the extension should *not* trigger.
4. Show both outputs. If the difference isn't visible, the extension isn't earning its cost — cut
   it back or drop it.

## 4. Commit and record

Commit it (committed config is what makes it shared — and cloud sessions only see repo-committed
skills). Note in the commit message which repeated failure it addresses, so the next configuration
review can judge whether it is still needed.

## Output

- **Layer chosen** and the trigger that justifies it
- **Files created**, with their context cost (always-loaded / description-only / zero until fired)
- **Evaluation** — baseline vs with-extension, on ≥3 cases, with real output
- **What it deliberately does not do** — the scope you kept it out of
