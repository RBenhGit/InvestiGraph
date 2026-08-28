---
name: custom-chart-set-prefix-string-duplicated
description: RESOLVED as of the chart-set-creation-UI diff (2026-07) — "custom:" is now the shared CUSTOM_CHART_SET_PREFIX constant in charts/registry.py, imported by __main__.py and web/app.py. Kept for history; nothing to flag here anymore unless a new call site reintroduces a bare literal.
metadata:
  type: project
---

**Update (2026-07):** fixed. `charts/registry.py` now exports `CUSTOM_CHART_SET_PREFIX =
"custom:"` with a docstring explaining it's shared with `__main__.py`/`web/app.py`; both of
those import it rather than hardcoding the literal, and `web/app.py`'s new `POST
/chart-sets` route (user-creatable named chart sets) also imports and checks against it
(rejects any user-submitted name starting with the prefix). `registry_test.py` imports the
constant too. Re-check this only if a future diff touches the prefix and doesn't import
the shared constant — the original finding below is now historical context, not a current
gap.

`__main__.py` and `web/app.py` each build an ad-hoc chart-set name as
`"custom:" + ",".join(sorted(chart_ids))` before calling `register_chart_set`.
`charts/registry.py`'s `registered_chart_sets()` (added 2026-07-25, commit `0ac4710`,
`feature/source-commissioning`) filters these out of the curated picker dropdown via a third,
independent copy of the same literal: `name.startswith("custom:")`.

**Why this matters:** none of the three occurrences import from a shared constant, and no test
exercises the real producer-to-filter path together — `registry_test.py`'s exclusion test
constructs the literal `"custom:eps,price"` directly rather than going through
`__main__.py`/`web/app.py`'s actual code. If a future diff renames the prefix in one producer
(e.g. to `"adhoc:"`) without updating `registry.py`'s filter, ad-hoc one-off chart sets would
start silently appearing as permanent options in the curated dropdown — the same "no shared
source of truth, nothing checks the copies stay in sync" shape as
[[registry-parallel-dicts-drift]], just a string instead of a dict key set.

**How to apply:** when reviewing a change to any of these three call sites, check whether the
other two still agree on the literal. Flag as Warning (not Critical — nothing is broken today)
if a shared constant isn't introduced and the change touches the prefix. Also worth suggesting
next time this area is touched: hoist `"custom:"` into a shared constant (e.g. in
`charts/registry.py`, exported for the two producers to import) so there's one source of truth.
