"""Disk-backed persistence for saved EPS valuations.

Ported from legacy/eps_evaluation/src/history/{store,index}.ts (see
docs/MERGE_SPEC.md, Phase 6). The original split those into an internal-only
`store.ts` (raw per-file JSON I/O) and a published `index.ts` (the
save/get/delete/get-all operations plus error formatting); this port keeps only
two files (`store.py`, `models.py`), so both layers live here.

Two behaviors are deliberately NOT a literal transliteration:

- Errors are raised as typed exceptions (`InvalidHistoryInput`, `ValuationNotFound`,
  or a plain `OSError`/`ValueError` for I/O and parse failures) instead of returned
  as a `{ ok, error }` result. This matches the rest of InvestiGraph's own
  convention (see `investigraph.sources.base`'s `TickerNotFound`, `SourceUnavailable`,
  etc., and how `web/app.py` catches them) rather than reproducing a TypeScript
  idiom in a codebase that already has its own idiomatic error handling.
- Writes go through an atomic temp-file + `os.replace` (see `write_history_file`)
  instead of writing the target file directly, reusing the pattern already
  established by `investigraph.cache.store.TemplateCache.put`. The original wrote
  directly and could truncate history.json on a crash mid-write.

Everything else -- file path resolution and precedence, the legacy-history merge on
read, malformed-entry filtering, and newest-first-with-replace-by-id saves --
preserves the original's behavior exactly.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from investigraph.history.models import (
    InvalidHistoryInput,
    SavedValuation,
    ValuationNotFound,
)

logger = logging.getLogger(__name__)

# Mirrors the original TS's `path.resolve(__dirname, '..', '..')` in
# src/history/store.ts (two directories above that file). This module lives at
# <repo root>/src/investigraph/history/store.py, so the repo root is three
# `.parent`s above it.
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def resolve_history_file_path(
    custom_path: str | Path | None = None, evaluator: str | None = None
) -> Path:
    """Resolve which JSON file backs a given (custom_path, evaluator) call.

    Precedence, matching the original exactly:
    1. An explicit `custom_path` wins outright, returned unresolved (as given) --
       the original never calls `path.resolve` on it either.
    2. The `HISTORY_FILE_PATH` env var, resolved to an absolute path. Checked
       BEFORE the evaluator, so setting it collapses per-evaluator storage back
       into a single shared file -- a documented consequence, not an accident.
    3. A sanitized `data/evaluators/<name>.json` for a non-blank evaluator (the
       name is trimmed, lower-cased, and stripped to `[a-z0-9_-]`).
    4. Otherwise, the root `history.json`.
    """
    if custom_path:
        return Path(custom_path)

    env_path = os.environ.get("HISTORY_FILE_PATH")
    if env_path:
        # os.path.abspath (not Path.resolve) to match Node's path.resolve: joins
        # with cwd and normalizes '.'/'..' lexically, without resolving symlinks.
        return Path(os.path.abspath(env_path))

    if evaluator and evaluator.strip():
        safe_name = re.sub(r"[^a-z0-9_-]", "", evaluator.strip().lower())
        return PROJECT_ROOT / "data" / "evaluators" / f"{safe_name}.json"

    return PROJECT_ROOT / "history.json"


def read_history_file(
    file_path: str | Path | None = None, evaluator: str | None = None
) -> list[SavedValuation]:
    """Read and parse a history file, tolerating a missing file and malformed rows.

    A missing file reads as an empty list. A non-array top-level JSON value also
    reads as an empty list. An entry that isn't an object with a string `ticker`
    field is dropped from the result and logged as a warning -- not silently --
    because a dropped row here is written back out of the array on the very next
    unrelated `save_valuation`/`delete_valuation` call (whatever this function
    returns is exactly what a subsequent write persists), so silently dropping it
    would turn a display-time glitch into permanent, unexplained data loss.
    """
    target = resolve_history_file_path(file_path, evaluator)
    try:
        raw = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []

    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        return []

    valid: list[SavedValuation] = []
    dropped = 0
    for item in parsed:
        if isinstance(item, dict) and isinstance(item.get("ticker"), str):
            try:
                valid.append(SavedValuation.model_validate(item))
                continue
            except ValidationError:
                pass
        dropped += 1

    if dropped:
        word = "entry" if dropped == 1 else "entries"
        logger.warning(
            "%s: dropped %d malformed %s (missing/non-string ticker)",
            target,
            dropped,
            word,
        )
    return valid


def write_history_file(
    records: list[SavedValuation],
    file_path: str | Path | None = None,
    evaluator: str | None = None,
) -> None:
    """Persist `records`, replacing the target file's contents atomically.

    Writes to a temp file in the same directory, then `os.replace`s it into place
    -- the same pattern as `TemplateCache.put`
    (src/investigraph/cache/store.py) -- so a crash or a concurrent reader never
    observes a partially-written file.
    """
    target = resolve_history_file_path(file_path, evaluator)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(
        [record.model_dump(mode="json", exclude_none=True) for record in records],
        indent=2,
    )
    tmp_path = target.with_suffix(f"{target.suffix}.tmp-{os.getpid()}")
    tmp_path.write_text(data, encoding="utf-8")
    os.replace(tmp_path, target)


def _now_iso() -> str:
    """Current UTC time as an ISO 8601 string with millisecond precision and a
    'Z' suffix, matching JavaScript's `Date.prototype.toISOString()`."""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _sort_key(record: SavedValuation) -> float:
    """Sort key for newest-first ordering. An unparseable/missing evaluated_at
    sorts as oldest, rather than raising -- a hand-edited record with a bad
    timestamp should not break the whole history read."""
    if not record.evaluated_at:
        return float("-inf")
    try:
        return datetime.fromisoformat(record.evaluated_at).timestamp()
    except ValueError:
        return float("-inf")


def save_valuation(
    input: SavedValuation, file_path: str | Path | None = None
) -> SavedValuation:
    """Save `input`, prepending it to the history and replacing any existing
    record with the same id.

    Assigns an id (`<epoch-ns>-<TICKER>`) and `evaluated_at` (now, ISO 8601) when
    `input` doesn't already supply them. Raises `InvalidHistoryInput` if `ticker`
    is blank.

    The original TS generated this id from `Date.now()` (millisecond resolution).
    Ported literally, two same-ticker saves within the same millisecond collide
    and the second silently overwrites the first via save_valuation's own
    replace-by-id semantics -- a real bug in the original design that its async
    fs I/O (each save awaits a real read+write round trip) happened to mask in
    practice. This port's I/O is synchronous and fast enough that two saves in a
    tight loop routinely land in the same millisecond, which turned the latent
    bug into a reliably-reproducing one (caught by
    test_filters_history_by_ticker_case_insensitively_and_sorts_newest_first).
    Nanosecond resolution removes the collision window; nothing else depends on
    the id's exact numeric format, only on it being a unique opaque string
    (confirmed: it's never parsed, only compared for equality or URL-encoded).
    """
    ticker = input.ticker.strip()
    if not ticker:
        raise InvalidHistoryInput("Ticker must be a non-empty string.")
    ticker = ticker.upper()

    evaluated_at = input.evaluated_at or _now_iso()
    id_ = input.id or f"{time.time_ns()}-{ticker}"
    evaluator = input.evaluator or None

    record = input.model_copy(
        update={
            "id": id_,
            "ticker": ticker,
            "evaluated_at": evaluated_at,
            "evaluator": evaluator,
        }
    )

    existing = read_history_file(file_path, evaluator)
    updated = [record] + [item for item in existing if item.id != id_]
    write_history_file(updated, file_path, evaluator)
    return record


def get_history(
    ticker: str | None = None,
    file_path: str | Path | None = None,
    evaluator: str | None = None,
) -> list[SavedValuation]:
    """Read a history view, newest first, optionally filtered by ticker
    (case-insensitive).

    Two merge behaviors layer on top of the raw per-evaluator/legacy file, both
    best-effort -- a corrupt or missing file involved in a merge must not fail the
    caller's own read:

    - With an evaluator and no explicit `file_path`, legacy `history.json` records
      that are unowned (no `evaluator` field) or owned by this same evaluator are
      folded in.
    - With no evaluator and no explicit `file_path`, every `data/evaluators/*.json`
      file is folded in too.

    Either way, a record already present (by id) from the primary read wins over
    one being merged in from a legacy/other file.
    """
    records = read_history_file(file_path, evaluator)

    if evaluator and not file_path:
        try:
            legacy = read_history_file()
            matching_legacy = [
                item
                for item in legacy
                if not item.evaluator or item.evaluator.lower() == evaluator.lower()
            ]
            existing_ids = {r.id for r in records}
            for leg in matching_legacy:
                if leg.id not in existing_ids:
                    records.append(leg)
        except Exception:
            # No legacy history.json (or it is unreadable) -- nothing to merge in,
            # the normal case for an install that only ever saved under an
            # evaluator.
            pass

    if not evaluator and not file_path:
        try:
            evaluators_dir = PROJECT_ROOT / "data" / "evaluators"
            try:
                files = sorted(p.name for p in evaluators_dir.iterdir())
            except Exception:
                # No data/evaluators/ directory yet -- nobody has saved under an
                # evaluator.
                files = []

            for file_name in files:
                if file_name.endswith(".json"):
                    ev = file_name[: -len(".json")]
                    ev_records = read_history_file(None, ev)
                    for r in ev_records:
                        if not r.evaluator:
                            r.evaluator = ev
                    existing_ids = {r.id for r in records}
                    for r in ev_records:
                        if r.id not in existing_ids:
                            records.append(r)
        except Exception:
            # Merging other evaluators' files is best-effort: a single unreadable
            # file must not fail the caller's own history read.
            pass

    filtered = records
    if ticker and ticker.strip():
        target = ticker.strip().upper()
        filtered = [item for item in records if item.ticker.upper() == target]

    filtered.sort(key=_sort_key, reverse=True)
    return filtered


def delete_valuation(
    id: str,
    file_path: str | Path | None = None,
    evaluator: str | None = None,
) -> SavedValuation:
    """Delete the record with `id`, checking the legacy `history.json` too in
    case there's a stranded copy there, or it was never in the evaluator-specific
    file.

    Raises `InvalidHistoryInput` if `id` is blank, or `ValuationNotFound` if `id`
    isn't present anywhere checked.
    """
    if not id or not id.strip():
        raise InvalidHistoryInput("ID must be a non-empty string.")

    existing = read_history_file(file_path, evaluator)
    deleted_item: SavedValuation | None = None
    found = False

    index = next((i for i, item in enumerate(existing) if item.id == id), -1)
    if index != -1:
        deleted_item = existing.pop(index)
        found = True
        write_history_file(existing, file_path, evaluator)

    if evaluator and not file_path:
        legacy = read_history_file()
        legacy_index = next((i for i, item in enumerate(legacy) if item.id == id), -1)
        if legacy_index != -1:
            deleted_legacy = legacy.pop(legacy_index)
            if deleted_item is None:
                deleted_item = deleted_legacy
            found = True
            write_history_file(legacy)

    if not found or deleted_item is None:
        raise ValuationNotFound(id)

    return deleted_item


def get_all_latest_valuations() -> list[SavedValuation]:
    """One record per (ticker, evaluator) pair -- the newest by `evaluated_at`.

    Keyed on the (ticker, evaluator) pair, not on ticker alone: two evaluators
    valuing the same ticker are two independent opinions, and keying on ticker
    alone would silently drop whichever was saved earlier. Legacy records with no
    evaluator collapse into a single '' bucket per ticker, preserving pre-evaluator
    behavior for them. A missing `data/evaluators/` directory just means nobody has
    saved under an evaluator yet; any other failure listing it is real and
    propagates rather than silently emptying the dashboard.
    """
    evaluators_dir = PROJECT_ROOT / "data" / "evaluators"
    try:
        files = sorted(p.name for p in evaluators_dir.iterdir())
    except FileNotFoundError:
        files = []

    all_records: list[SavedValuation] = list(read_history_file())

    for file_name in files:
        if file_name.endswith(".json"):
            evaluator = file_name[: -len(".json")]
            records = read_history_file(None, evaluator)
            for r in records:
                if not r.evaluator:
                    r.evaluator = evaluator
            all_records.extend(records)

    latest_by_ticker_and_evaluator: dict[str, SavedValuation] = {}
    for record in all_records:
        # NUL-separated key so an evaluator name containing the separator can't
        # collide across buckets.
        key = f"{record.ticker}\x00{(record.evaluator or '').lower()}"
        existing = latest_by_ticker_and_evaluator.get(key)
        if existing is None or _sort_key(record) > _sort_key(existing):
            latest_by_ticker_and_evaluator[key] = record

    return list(latest_by_ticker_and_evaluator.values())
