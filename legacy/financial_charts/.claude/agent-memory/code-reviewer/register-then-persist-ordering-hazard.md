---
name: register-then-persist-ordering-hazard
description: web/app.py's POST /chart-sets calls register_chart_set() (in-memory, live) before chart_set_store.save() (disk) — if the disk write fails, the name is permanently "phantom registered" in-process (blocking retries) but never persisted, and the client gets an unhandled 500 instead of the route's normal JSON error contract.
metadata:
  type: project
---

`web/app.py`'s `POST /chart-sets` route (added alongside `web/chart_set_store.py`,
2026-07) does, in order:

```python
register_chart_set(name, charts)   # in-memory, immediate
store.save(name, chart_ids)        # disk, can raise (permissions, disk full, etc.)
```

If `store.save()` raises, the exception is unhandled by the route (every other failure
mode in this route returns a clean `{"error": ...}` 400 via early `return`) — Flask falls
through to its default 500 HTML error page, which breaks the frontend's `response.json()`
parse and surfaces as a generic "Network error" in the UI, not the real cause.

Worse: `register_chart_set` already ran, so the name is now live in the process-global
`_CHART_SETS` registry (visible in the dropdown, appears in `registered_chart_sets()`) even
though it was never durably saved. Two consequences: (1) it silently vanishes on the next
real server restart with no record it ever "succeeded," and (2) the user can't retry with
the same name in the meantime — the route's own `if name in registered_chart_sets():
already exists` check now blocks them, even though nothing was actually saved.

**How to apply:** when reviewing a route that does a "register live" + "persist to disk"
pair (or any two side effects where the first is irreversible/immediately-visible and the
second can fail), check the ordering. Prefer persist-first-then-register (a failed persist
then leaves zero visible state change, matching the route's other clean-400 failure modes)
or wrap the pair so a persist failure rolls back the registration. Flag as Warning, not
Critical, unless the diff's own error-handling elsewhere in the same route establishes a
"every failure is a clean typed error" contract that this ordering silently breaks (it does,
here — see `web/app.py`'s `/chart-sets` route, every other branch returns `jsonify(error=...)`,
400).
