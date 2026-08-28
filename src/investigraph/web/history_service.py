"""Orchestration for the history/valuations routes, composed only from
`history/store.py`'s published functions and `web/case_conversion.py`.

Ported from Eps_Evaluation's GET/POST /api/history, DELETE /api/history/:id,
and GET /api/valuations handlers (legacy/eps_evaluation/src/web/server.ts).
Every request/response body crosses the camelCase (verbatim front end) <->
snake_case (this codebase's Pydantic models) boundary here — see
`case_conversion.py`'s module docstring.

Exception mapping (found in the Phase 4-6 convergence review, before this
module existed): `history/store.py`'s `read_history_file` can raise a bare
`json.JSONDecodeError` or `OSError` (documented in its own docstring) on a
corrupt or unreadable history file — `json.JSONDecodeError` is a `ValueError`
subclass, so `except (OSError, ValueError)` catches both without importing
`json` directly. Every function below maps that to the same `IO_ERROR` shape
the original used for its own uncaught-error path, instead of letting it
become an unhandled Flask 500 with a leaked traceback.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from investigraph.history.models import (
    InvalidHistoryInput,
    SavedValuation,
    ValuationNotFound,
)
from investigraph.history.store import (
    delete_valuation,
    get_all_latest_valuations,
    get_history,
    save_valuation,
)
from investigraph.web.case_conversion import keys_to_camel_case, keys_to_snake_case


@dataclass
class HistoryError(Exception):
    status: int
    error: dict[str, Any]


def _to_camel(record: SavedValuation) -> dict[str, Any]:
    return keys_to_camel_case(record.model_dump(mode="json", exclude_none=True))


def list_history(ticker: str | None, evaluator: str | None) -> list[dict[str, Any]]:
    try:
        records = get_history(ticker, None, evaluator)
    except (OSError, ValueError) as exc:
        raise HistoryError(500, {"type": "IO_ERROR", "message": str(exc)}) from exc
    return [_to_camel(record) for record in records]


def create_valuation(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        record = SavedValuation(**keys_to_snake_case(payload))
    except ValidationError as exc:
        raise HistoryError(400, {"type": "INVALID_INPUT", "reason": str(exc)}) from exc
    try:
        saved = save_valuation(record)
    except InvalidHistoryInput as exc:
        raise HistoryError(400, {"type": "INVALID_INPUT", "reason": str(exc)}) from exc
    except (OSError, ValueError) as exc:
        raise HistoryError(500, {"type": "IO_ERROR", "message": str(exc)}) from exc
    return _to_camel(saved)


def remove_valuation(id_: str, evaluator: str | None) -> dict[str, Any]:
    try:
        deleted = delete_valuation(id_, None, evaluator)
    except InvalidHistoryInput as exc:
        raise HistoryError(400, {"type": "INVALID_INPUT", "reason": str(exc)}) from exc
    except ValuationNotFound as exc:
        raise HistoryError(404, {"type": "NOT_FOUND", "id": id_}) from exc
    except (OSError, ValueError) as exc:
        raise HistoryError(500, {"type": "IO_ERROR", "message": str(exc)}) from exc
    return _to_camel(deleted)


def list_all_latest_valuations() -> list[dict[str, Any]]:
    try:
        records = get_all_latest_valuations()
    except (OSError, ValueError) as exc:
        raise HistoryError(500, {"type": "IO_ERROR", "message": str(exc)}) from exc
    return [_to_camel(record) for record in records]
