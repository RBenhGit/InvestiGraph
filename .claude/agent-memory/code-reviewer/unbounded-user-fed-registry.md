---
name: unbounded-user-fed-registry
description: charts/registry.py's _CHART_SETS dict grows one entry per unique chart-id combination a caller registers, and nothing ever evicts — feature code that lets user input (CLI flags or web query params) drive the registration key can turn this into unbounded, request-triggerable memory growth.
metadata:
  type: project
---

`charts/registry.py`'s `register_chart_set(name, charts)` is a plain `_CHART_SETS[name] = charts`
dict assignment with no eviction, no TTL, no size cap — it lives for the process lifetime.
That's fine for the small number of hardcoded named sets it was built for (e.g.
`"fundamentals"`), but the "chart picker" feature (added ~2026-07, `__main__.py` /
`web/app.py`) generates the registration key directly from user-submitted chart ids
(`"custom:" + ",".join(sorted(chart_ids))`), with no dedup of the input list.

**Why this matters:** a client can grow `_CHART_SETS` forever in a single burst just by
padding a query string with repeated values (e.g. `?charts=price&charts=price&charts=price...`
with a different repeat count each time) — every distinct string produces a new permanent
dict entry, verified experimentally (19 padded variants of one id produced 19 new entries).
Contrast with `cache/store.py`'s on-disk cache, whose key is bounded by real business
dimensions (ticker × source × period × range × date) — still grows over long real-world
time, but not by an attacker/script alone in one session.

The same missing-dedup also means a caller can request `charts=price,price` and get the
`price` chart rendered twice (no corruption, just a visibly broken duplicate card) — this
was untested in the diff that introduced it.

**How to apply:** whenever a future diff feeds a global module-level dict/list registry
(in this codebase or a similar one) from raw user/CLI input without deduping the input or
bounding/evicting the registry, flag it — both the duplicate-rendering edge case and the
unbounded-growth-over-a-long-lived-process risk. Ask whether the registry should dedupe the
input list and/or key by a canonical (already-deduped, already-sorted) form, and whether a
long-running server process needs any cap/eviction at all given the surface is directly
reachable from HTTP query params. Related: [[registry-parallel-dicts-drift]] (a different
registry-hygiene gap in the same codebase, in `sources/registry.py`).

**Update (2026-07):** a second, now-*durable* growth vector was added: `web/app.py`'s
`POST /chart-sets` route lets a user name-and-save an arbitrary chart selection, which both
`register_chart_set()`s it (same never-evicted `_CHART_SETS`) AND persists it to
`.cache/financial_charts/chart_sets.json` via the new `web/chart_set_store.py`
(`ChartSetStore`) — `create_app()` bootstrap-reloads every persisted entry on every startup.
This is more *bounded* in practice than the raw-query-param vector above (it requires a
deliberate name + at least one real chart id, not an auto-generated key from padded query
params), but it changes the growth from "wiped by every restart" to "permanent unless the
JSON file is manually edited." Not flagged as a new defect — deliberate, user-driven,
matches the feature's purpose — but worth knowing this store is the second contributor to
`_CHART_SETS` size, not just the ad-hoc `custom:`-prefixed one. See also
[[chart-set-store-load-shape-not-validated]] for a related, more concrete bug in the same
new store.

Separately, note that `web/__main__.py` runs the Flask dev server with `threaded=False`
specifically because matplotlib's pyplot isn't thread-safe — this happens to make any
shared-mutable-global-dict write from concurrent requests moot *today*, but it's an
invariant the registry code doesn't own or enforce. If a future diff ever flips
`threaded=True` or moves this app behind a multi-threaded WSGI server, revisit whether
`register_chart_set` writes from concurrent requests are still safe (in this codebase,
CPython dict assignment itself won't corrupt the dict, but two concurrent requests with the
same chart *set* submitted in a different *order* could race and one render the other's
chart order).
