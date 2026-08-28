---
name: pre-merge-reviewer-memory-collection
description: The real code-reviewer memory collection for this codebase lives under legacy/financial_charts/.claude/agent-memory/code-reviewer/, not the repo-root .claude/ — read its MEMORY.md before any review
metadata:
  type: reference
---

InvestiGraph's accumulated code-reviewer memories (10+ entries, built up across Financial_Charts'
own history) are at `legacy/financial_charts/.claude/agent-memory/code-reviewer/MEMORY.md`, not at
the repo-root `.claude/agent-memory/code-reviewer/` that the agent config points at. Phase 3 of the
merge deliberately left `legacy/financial_charts/.claude/` in place; reconciling the two locations
is Phase 9's job (see `PROGRESS.md`).

**How to apply:** read that MEMORY.md index at the start of every review here until Phase 9 merges
the two. Entries that recur in practice: `money-currency-guard-bypassed-via-raw-division`,
`review_series_positional_indexing`, `skipped-points-interpolate-across-gaps`. New findings during
the merge have been written into that collection (e.g. the Phase 5 positional-indexing one), so
writing only to the root dir risks splitting the collection further.
See [[valuation-chain-drops-money-currency-tag]].
