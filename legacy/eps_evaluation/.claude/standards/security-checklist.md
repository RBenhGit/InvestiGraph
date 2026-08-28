# Security Review Standard

> **Provenance.** Distilled from the CodeFundation wiki pages `specialized-agent-roles` and
> `verification-loops` (upstream: `claude-docs-best-practices`, `claude-docs-subagents`,
> `voltagent-subagents-catalog`, `official-marketplace-2026-08`). Defensive review only.

## Contents

1. Scope and trust boundaries
2. The review categories
3. The refutation protocol (mandatory)
4. Output format
5. What not to report

---

## 1. Scope and trust boundaries

Review **the diff**, plus enough surrounding code to judge it. Before reading the diff, write
down the project's trust boundaries — the places where data or control crosses from less-trusted
to more-trusted:

- Network input (HTTP handlers, webhooks, websockets, queue consumers)
- User-supplied files and filenames
- Environment/config and secrets material
- Anything crossing a privilege change (auth, role elevation, impersonation, admin paths)
- Anything crossing a process boundary (shell, subprocess, SQL, template, deserializer)

A finding is interesting in proportion to the boundary it crosses. A missing null check inside a
pure function is not a security finding.

## 2. The review categories

Work these in order. For each, the question to ask, not just the label.

**Injection** — does untrusted data reach an interpreter as code?
SQL/ORM raw fragments, shell invocation with string concatenation, template rendering with
user data, `eval`-family calls, path traversal into file APIs, log injection into structured logs,
deserialization of untrusted payloads.

**AuthN / AuthZ** — who is allowed to do this, and where is that checked?
Missing authorization on a new endpoint or action; checks performed on the client only; object-level
authorization missing (the user is authenticated, but is *this* their record?); role checks that
read from user-controlled input; new code paths that bypass an existing guard.

**Secrets** — is credential material exposed or persisted where it shouldn't be?
Hardcoded keys/tokens/passwords, secrets in logs or error messages, secrets committed to config
files, credentials in URLs, secrets echoed back to clients in debug output.

**Insecure data handling** — what happens to sensitive data at rest, in transit, and in errors?
Missing input validation at the boundary (as opposed to deep inside), unbounded input sizes,
PII in logs, disabled TLS verification, weak or hand-rolled crypto, predictable identifiers where
unguessability is a security property, error messages that leak internals.

**Secondary sweep** (only if the diff touches them): CSRF/CORS changes, cookie flags, redirect
targets, file upload handling, rate limiting on newly exposed endpoints, dependency additions
with known-vulnerable versions.

## 3. The refutation protocol (mandatory)

A reviewer asked to find problems will find them. Unsupported security findings are expensive:
they push the implementer toward defensive code and abstractions the task never needed, and they
train the team to ignore the reviewer.

So: for **every** candidate finding, before it reaches the report, try to refute it.

1. **Trace the input.** Can attacker-controlled data actually reach this line? Show the path from
   the boundary to the sink. If you cannot, drop it.
2. **Check the callers.** Is validation, escaping, or an authorization check already applied
   upstream — including by a framework or middleware? If yes, drop it.
3. **State the exploit in one sentence.** "An unauthenticated caller can pass `X` to `Y` and
   obtain/modify `Z`." If you cannot write that sentence with concrete values, drop it.

Report the **count of candidates dropped**. The count is evidence that the protocol ran; the
official `claude-security` pipeline computes its verification tally in code for the same reason.

## 4. Output format

Severity-graded, most severe first. For each finding:

- `file:line`
- **Category** (§2)
- **The exploit sentence** from §3.3 — inputs, path, impact
- **Fix** — the smallest change that closes it, in one or two lines
- Severity: **Critical** (exploitable now, crosses a trust boundary) / **High** (exploitable given
  a plausible precondition) / **Medium** (defense-in-depth gap with a real path) — no lower tiers

Close with:
- **Dropped:** N candidates refuted (one line each on why)
- **Verdict:** safe to merge / must fix before merge
- **Not reviewed:** anything you could not judge (a dependency's internals, generated code, an
  unavailable schema) — say so rather than implying coverage you don't have

## 5. What not to report

- Findings you cannot reach from a boundary
- Generic hardening advice unrelated to the diff ("consider adding a WAF")
- Missing tests, style, performance, architecture — other agents own those
- Theoretical weaknesses in vetted libraries used correctly
- Anything that requires an attacker to already have the privilege the finding would grant
