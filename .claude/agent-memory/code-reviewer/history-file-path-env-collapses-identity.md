---
name: history-file-path-env-collapses-identity
description: HISTORY_FILE_PATH is checked before the evaluator branch in resolve_history_file_path, so anything built on store's path resolution collapses all evaluators onto one file — identity code must re-apply the slug rule instead.
metadata:
  type: project
---

`history/store.py`'s `resolve_history_file_path` checks `HISTORY_FILE_PATH`
(env var) at step 2, **before** the per-evaluator branch at step 3. Consequence:
with that env var set, every evaluator name resolves to the same path.

That is correct and documented for *storing records*, but it is wrong for any
code that needs evaluator **identity** (who exists, what their slug is). Building
identity on `resolve_history_file_path(...).stem` or `read_history_file(...)`
means that under the env var every name collapses to one entry.

`history/evaluators.py` (added 2026-09) deliberately re-applies the sanitizing
regex `re.sub(r"[^a-z0-9_-]", "", name.strip().lower())` and reads the
per-evaluator JSON files directly, rather than calling store's helpers, for
exactly this reason. Verified: mutating `_slug` to delegate to
`resolve_history_file_path` makes
`test_identities_survive_the_history_file_path_env_var` fail.

The duplicated regex is therefore intentional, not drift — but it *is* a
two-copy invariant. If store.py's sanitizing rule ever changes, existing
`data/evaluators/<slug>.json` filenames change with it and evaluators.py must
change in lockstep or the union stops matching files to names.

**Test-fixture trap:** `web/history_route_test.py`'s `client` fixture sets
`HISTORY_FILE_PATH`, so it can never exercise per-evaluator storage. Evaluator
tests must use `monkeypatch.setattr(store, "PROJECT_ROOT", tmp_path)` plus
`monkeypatch.delenv("HISTORY_FILE_PATH", raising=False)` instead.

**How to apply:** when reviewing anything that enumerates or identifies
evaluators, check it does not route through store's path resolution. When
reviewing a change to store.py's sanitizing regex, check `evaluators.py::_slug`
changed too.
