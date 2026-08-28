---
name: chart-set-store-load-shape-not-validated
description: web/chart_set_store.py's load() only checks the top-level JSON is a dict, not that each value is a list[str] — a malformed entry crashes create_app() at startup instead of degrading, unlike the TemplateCache pattern it claims to mirror.
metadata:
  type: project
---

`web/chart_set_store.py`'s `ChartSetStore.load()` docstring/design intent (mirrors
`cache/store.py`'s `TemplateCache`) promises "missing or corrupt file treated as empty
rather than a crash," and has tests for corrupt JSON syntax and non-dict top-level JSON.
But it only validates the **top-level** shape (`isinstance(data, dict)`) — it never checks
that each value is a `list[str]`.

`cache/store.py`'s `TemplateCache._load()` avoids this class of bug entirely because it
delegates to `CompanyFundamentals.model_validate_json()` — full Pydantic schema validation
catches any shape mismatch as a `ValueError` and falls back to "miss." `ChartSetStore` has
no schema, just a bare `json.loads()` + one `isinstance` check, so it doesn't get that
protection for free.

**Concrete repro** (verified in this codebase, `web/app.py`'s `create_app()` bootstrap
loop): write `{"foo": 5}` (or `{"foo": null}`) to the store file, then call
`create_app(chart_set_store=ChartSetStore(that_dir))`. The bootstrap loop does
`for chart_id in chart_ids` inside a `try: ... except KeyError: continue` — but iterating
a non-iterable (`int`, `None`, `bool`, `float`) raises `TypeError`, not `KeyError`, so it's
uncaught and crashes `create_app()` itself, taking down the whole server at startup, not
just the one malformed entry.

Not reachable via `POST /chart-sets` today (the only writer, `_dedup_chart_ids()`, always
produces `list[str]` before `save()` is called) — this needs manual file editing or a future
schema change to trigger. Still worth flagging as Critical when found: the blast radius is
total (whole app won't start, not just one degraded chart set), and the code's own tests
show the author intended full corruption-safety, just didn't cover this case.

**How to apply:** whenever a future diff adds a hand-rolled (non-Pydantic) disk-persisted
dict/list store in this codebase, check that `load()` validates the *shape of every value*,
not just the top-level container — and that every *caller* of `load()` treats a malformed
per-entry value the same way it treats a missing file (skip/empty), not as an uncaught
exception. Related: [[unbounded-user-fed-registry]] (a different `chart_set_store`-adjacent
gap, about growth rather than crash-safety).
