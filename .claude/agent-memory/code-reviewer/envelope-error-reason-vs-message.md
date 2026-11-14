---
name: envelope-error-reason-vs-message
description: app.js's {ok, error} envelope carries error.reason for 400 INVALID_INPUT but error.message for 500 IO_ERROR; new fetch handlers that read only one of the two alert "undefined" on the other path.
metadata:
  type: project
---

`web/history_service.py` raises `HistoryError` with **two different error shapes**
depending on the failure class:

- `InvalidHistoryInput` -> 400 `{"type": "INVALID_INPUT", "reason": str(exc)}`
- `(OSError, ValueError)` -> 500 `{"type": "IO_ERROR", "message": str(exc)}`

So `error.reason` and `error.message` are each present in only one of the two cases.
The established front-end idiom that handles this correctly is in `app.js`'s save
handler (around the `handleSaveValuation` error branch):

```js
const errMsg =
  (body && body.error && body.error.message) ||
  (body && body.error && body.error.reason) ||
  (body && body.message) ||
  'Failed to save.';
```

New handlers that read only `body.error.reason` render the literal string
`undefined` to the user on any 500 (reproduced: chmod 000 on `data/evaluators.json`,
then POST /api/evaluators -> 500 IO_ERROR with only `message`). Found in the
evaluator-picker change (2026-09) in both the `+` and `-` click handlers.

**Why:** the service layer's two `except` clauses were written independently and
never converged on one key name; the front end has to tolerate both.

**How to apply:** whenever reviewing a new `fetch` handler against any route backed
by `history_service.py` (or any service using the same `HistoryError` dataclass),
check that the error-message extraction falls back across `message` *and* `reason`.
Flag as a Warning. The deeper fix would be unifying the two shapes in
`history_service.py`, but that is a wider change than most diffs should take on.
