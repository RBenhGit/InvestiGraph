"""The evaluator registry: who exists, and who is currently selected.

Companion to `store.py`, which owns what each evaluator has *saved*. This module
owns the orthogonal question of who exists at all, backed by a single sidecar
file, `data/evaluators.json`:

    {"evaluators": ["Aviv", "Ran"], "selected": "Aviv"}

Why a sidecar rather than reusing the per-evaluator files: those are bare JSON
*arrays* of records, and `store.read_history_file` treats any non-array top-level
value as empty, so there is nowhere in that format to hang a display name and no
way to add one without breaking every existing read. Deriving the list from
filenames alone doesn't work either -- `resolve_history_file_path` sanitizes a
name down to `[a-z0-9_-]`, which is lossy ("Aviv Cohen" -> "avivcohen"),
one-way, and can collide two distinct names onto one file.

The registry is therefore the source of truth for display names, but it is not
the only source of truth for existence: `list_evaluators` unions it with the
names recoverable from `data/evaluators/*.json`. That union is what lets this
module be deployed against an existing installation with no migration step, and
what lets a deleted or corrupt registry rebuild itself from the valuation files
that survive.

This module reads the per-evaluator files directly rather than through
`store.read_history_file`, and re-applies the slug rule rather than calling
`store.resolve_history_file_path`. Both for one reason: those functions honor
`HISTORY_FILE_PATH`, which collapses every evaluator onto a single shared file.
That is correct for storing records but wrong for enumerating identities -- under
that env var, every name would resolve to the same path and the registry would
report one evaluator. Identity must not depend on where records are stored.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

from investigraph.history.models import InvalidHistoryInput

logger = logging.getLogger(__name__)

# The names a fresh installation starts with, matching the default the front end
# used to hard-code in localStorage before the list moved server-side.
DEFAULT_EVALUATORS = ["Aviv", "Ran"]


def registry_path() -> Path:
    """Location of the sidecar registry file.

    Derived from `PROJECT_ROOT` at call time rather than bound at import time so
    that tests monkeypatching `store.PROJECT_ROOT` redirect this too.
    """
    from investigraph.history import store

    return store.PROJECT_ROOT / "data" / "evaluators.json"


def evaluators_dir() -> Path:
    from investigraph.history import store

    return store.PROJECT_ROOT / "data" / "evaluators"


def _slug(name: str) -> str:
    """The on-disk slug for a display name.

    Deliberately re-applies `resolve_history_file_path`'s rule (trim, lower-case,
    strip to `[a-z0-9_-]`) rather than calling it and reading the filename back:
    that function checks `HISTORY_FILE_PATH` *first*, so under that env var every
    name would resolve to one shared path and every slug would come back
    identical. A slug is an identity here, not a location, so it must not depend
    on where the records happen to be stored.

    Returns "" for a name that sanitizes away entirely (e.g. an all-non-ASCII
    name), which callers must reject -- such a name would otherwise land in
    `data/evaluators/.json`.
    """
    return re.sub(r"[^a-z0-9_-]", "", name.strip().lower())


def _names_on_disk() -> list[str]:
    """Display names recovered from the per-evaluator valuation files.

    The filename is only a slug, so the pretty casing is recovered from the
    `evaluator` field of the first record that carries one -- the same trick
    `store.get_all_latest_valuations` uses. A file with no usable record (an
    empty one, freshly created by `add_evaluator`) falls back to its slug.
    """
    try:
        files = sorted(p.name for p in evaluators_dir().iterdir())
    except FileNotFoundError:
        return []
    except OSError:
        # Listing failed for a real reason (permissions, a file where the
        # directory should be). Best-effort: the registry alone still answers.
        logger.warning("Could not list %s; using the registry alone", evaluators_dir())
        return []

    names: list[str] = []
    for file_name in files:
        if not file_name.endswith(".json"):
            continue
        slug = file_name[: -len(".json")]
        if not slug:
            continue
        names.append(_display_name(evaluators_dir() / file_name, slug))
    return names


def _display_name(path: Path, slug: str) -> str:
    """Recover an evaluator's pretty casing from their valuation file.

    The filename carries only the slug, so the display name comes from the
    `evaluator` field of the first record that has one -- the same recovery
    `store.get_all_latest_valuations` performs. A file with no usable record (an
    empty one, freshly created by `add_evaluator`) falls back to the slug.
    """
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # A corrupt or unreadable valuation file must not blank the whole
        # dropdown; the evaluator still exists, just under its slug.
        logger.warning("Could not read %s; using its slug as-is", path.name)
        return slug

    if not isinstance(parsed, list):
        return slug
    for record in parsed:
        if isinstance(record, dict):
            evaluator = record.get("evaluator")
            if isinstance(evaluator, str) and evaluator.strip():
                return evaluator.strip()
    return slug


def _has_records(slug: str) -> bool:
    """Whether an evaluator's file holds at least one record.

    Read directly (not via `store.read_history_file`) for the env-var reason in
    the module docstring. A file we cannot parse counts as having records: it is
    strictly safer to keep a file we can't read than to delete one that may hold
    real valuations.
    """
    path = evaluators_dir() / f"{slug}.json"
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False
    except (OSError, ValueError):
        logger.warning("Could not read %s.json; treating it as non-empty", slug)
        return True
    return bool(parsed) if isinstance(parsed, list) else True


def _merge(primary: list[str], extra: list[str]) -> list[str]:
    """`primary` in order, then any of `extra` not already present.

    Matching is case-insensitive on the slug, so "Ran" and "R.A.N." -- which
    share one file -- are one entry, and the registry's casing wins.
    """
    merged = list(primary)
    seen = {_slug(name) for name in primary}
    for name in extra:
        key = _slug(name)
        if key and key not in seen:
            seen.add(key)
            merged.append(name)
    return merged


def read_registry() -> dict[str, object]:
    """Parse the sidecar, tolerating every way it can be absent or malformed.

    Mirrors `store.read_history_file`'s posture: a missing file, a non-object
    top-level value, or a missing/wrong-typed key degrades to the default rather
    than raising, because an unreadable registry must not take down the page. A
    genuinely unreadable file (permissions) still raises `OSError`, which the
    service layer maps to a 500.
    """
    target = registry_path()
    try:
        raw = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {"evaluators": list(DEFAULT_EVALUATORS), "selected": None}

    try:
        parsed = json.loads(raw)
    except ValueError:
        logger.warning("%s is not valid JSON; falling back to the defaults", target)
        parsed = None

    if not isinstance(parsed, dict):
        return {"evaluators": list(DEFAULT_EVALUATORS), "selected": None}

    raw_names = parsed.get("evaluators")
    names = (
        [n.strip() for n in raw_names if isinstance(n, str) and n.strip()]
        if isinstance(raw_names, list)
        else list(DEFAULT_EVALUATORS)
    )

    selected = parsed.get("selected")
    if not isinstance(selected, str) or not selected.strip():
        selected = None

    return {"evaluators": names, "selected": selected}


def write_registry(evaluators: list[str], selected: str | None) -> None:
    """Persist the sidecar atomically (temp file + `os.replace`).

    The same pattern as `store.write_history_file`, so a crash or a concurrent
    reader never observes a half-written registry.
    """
    target = registry_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps({"evaluators": evaluators, "selected": selected}, indent=2)
    tmp_path = target.with_suffix(f"{target.suffix}.tmp-{os.getpid()}")
    tmp_path.write_text(data, encoding="utf-8")
    os.replace(tmp_path, target)


def list_evaluators() -> dict[str, object]:
    """The full picture the UI needs: every known name, and the current selection.

    The selection is resolved, not echoed: a stored selection that no longer
    matches a known evaluator (that evaluator was removed) falls back to the
    first name, so the caller never renders a dropdown whose selected value
    isn't one of its options.
    """
    registry = read_registry()
    names = _merge(list(registry["evaluators"]), _names_on_disk())

    selected = registry["selected"]
    known = {_slug(name) for name in names}
    if not isinstance(selected, str) or _slug(selected) not in known:
        selected = names[0] if names else None

    return {"evaluators": names, "selected": selected}


def add_evaluator(name: str) -> dict[str, object]:
    """Register `name`, and create its (empty) valuation file.

    Creating `data/evaluators/<slug>.json` as `[]` up front is what makes the
    evaluator exist for every other terminal immediately, rather than only once
    they have saved their first valuation -- which is the whole point of moving
    this off per-browser storage.
    """
    if not name or not name.strip():
        raise InvalidHistoryInput("Evaluator name is required")

    cleaned = name.strip()
    slug = _slug(cleaned)
    if not slug:
        raise InvalidHistoryInput(
            f"Evaluator name {cleaned!r} contains no usable characters "
            "(only letters a-z, digits, '_' and '-' are kept)"
        )

    registry = read_registry()
    names = list(registry["evaluators"])

    # Idempotent: adding an existing name (in any casing, or any spelling that
    # shares its slug) is a no-op rather than a duplicate row.
    if slug not in {_slug(existing) for existing in names}:
        names.append(cleaned)

    write_registry(names, registry["selected"])

    target = evaluators_dir() / f"{slug}.json"
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("[]", encoding="utf-8")

    return list_evaluators()


def remove_evaluator(name: str) -> dict[str, object]:
    """Drop `name` from the registry, leaving its saved valuations untouched.

    Deliberately cosmetic, matching the confirmation the UI has always shown
    ("History files are not deleted"). Because `list_evaluators` unions the
    registry with what is on disk, an evaluator who still has saved valuations
    reappears -- correct, since the alternative is a dropdown that silently
    hides real data. Only an evaluator with no valuations (an empty file, or
    none) actually disappears.
    """
    if not name or not name.strip():
        raise InvalidHistoryInput("Evaluator name is required")

    cleaned = name.strip()
    slug = _slug(cleaned)
    registry = read_registry()
    names = [n for n in registry["evaluators"] if _slug(n) != slug]

    selected = registry["selected"]
    if isinstance(selected, str) and _slug(selected) == slug:
        selected = None

    write_registry(names, selected)

    # An evaluator whose file holds no records is one this registry invented;
    # remove it so the name doesn't come straight back through the disk union.
    target = evaluators_dir() / f"{slug}.json"
    if slug and target.exists() and not _has_records(slug):
        try:
            target.unlink()
        except OSError:
            logger.warning("Could not remove %s; leaving it in place", target.name)

    return list_evaluators()


def set_selected(name: str) -> dict[str, object]:
    """Record which evaluator is currently selected.

    Note this is a single global value: the app has no user or session model, so
    two browsers pointed at one server share it. That is the intended behavior
    (the terminal is a pure display), but it is the one field to revisit if
    per-terminal selection is ever wanted.
    """
    if not name or not name.strip():
        raise InvalidHistoryInput("Evaluator name is required")

    cleaned = name.strip()
    registry = read_registry()
    names = _merge(list(registry["evaluators"]), _names_on_disk())
    if _slug(cleaned) not in {_slug(n) for n in names}:
        raise InvalidHistoryInput(f"Unknown evaluator {cleaned!r}")

    write_registry(list(registry["evaluators"]), cleaned)
    return list_evaluators()
