---
name: registry-parallel-dicts-drift
description: sources/registry.py keeps adapter and capability lookups in two separately hand-maintained dicts that can silently drift out of sync
metadata:
  type: project
---

`src/financial_charts/sources/registry.py` maps source name -> implementation twice:
`_ADAPTERS: dict[str, type[DataSource]]` and `_CAPABILITIES: dict[str, Capability]`. Both are
populated by hand, one entry per source, with no shared source of truth and no test/assertion
that their key sets match.

Confirmed by reproduction (2026-07-19, feature/capability-viewer branch, commit
`7e60bc7 Add capabilities CLI subcommand for offline source inspection`): if a source is added
to `_ADAPTERS` but the matching `_CAPABILITIES` entry is forgotten, `registered_sources()`
(derived only from `_ADAPTERS`) lists the new source, but `get_capability()` then raises an
uncaught `KeyError` for it — e.g. `financial_charts capabilities` (no args, "list all" path)
crashes with a raw traceback instead of a clean per-source error, because that code path doesn't
wrap the lookup in try/except the way the single-name path does.

**Why:** the two dicts are independently maintained with no linkage; nothing in the code or
test suite enforces `set(_ADAPTERS) == set(_CAPABILITIES)`.

**How to apply:** when reviewing any future change that adds/removes a source in
`sources/registry.py` (or adds another parallel per-source dict for some other purpose, e.g. a
future `_VALIDATORS` or similar), check whether the new/changed dict's key set is verified
against `_ADAPTERS` — either by a test asserting equal key sets, or by deriving one dict from
the other, or by a module-level assertion. Flag as Critical if a "list all sources" code path
iterates one dict's keys and indexes into another dict without a guard, since that reproduces
this exact crash.
