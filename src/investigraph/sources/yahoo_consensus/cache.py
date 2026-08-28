"""Disk cache for `AnalystConsensus`, keyed by (ticker, date), 24h TTL.

A sibling of `cache/store.py`'s `TemplateCache` — same atomic temp-file +
`os.replace` write pattern, same standalone shape (an orchestration layer reads
cache-first and calls `adapter.fetch_analyst_consensus` on a miss, the way
`web/service.py` already does for `TemplateCache`; this module doesn't do that
wiring itself). It differs from `TemplateCache` in one way: `TemplateCache` never
expires an entry on its own (a stale entry is only ever served deliberately, via
`latest()`, when a live fetch fails) — this cache actively expires past a fixed
TTL, porting Eps_Evaluation's `DEFAULT_YAHOO_CACHE_TTL_MS` (24h) read-through
behavior (legacy/eps_evaluation/src/data/yahoo/index.ts).
"""

import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from investigraph.sources.yahoo_consensus.models import AnalystConsensus

_DEFAULT_CACHE_DIR = Path(".cache") / "investigraph" / "yahoo_consensus"
_DEFAULT_TTL = timedelta(hours=24)


def _key(ticker: str, as_of: date) -> str:
    return f"{ticker.upper()}_{as_of.isoformat()}"


class AnalystConsensusCache:
    def __init__(
        self,
        cache_dir: Path | str = _DEFAULT_CACHE_DIR,
        ttl: timedelta = _DEFAULT_TTL,
    ):
        self._dir = Path(cache_dir)
        self._ttl = ttl

    def _path(self, ticker: str, as_of: date) -> Path:
        return self._dir / f"{_key(ticker, as_of)}.json"

    def get(self, ticker: str, as_of: date) -> AnalystConsensus | None:
        path = self._path(ticker, as_of)
        if not path.exists():
            return None
        consensus = _load(path)
        if consensus is None or self._is_expired(consensus):
            return None
        return consensus

    def put(self, ticker: str, as_of: date, consensus: AnalystConsensus) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._path(ticker, as_of)
        # Write to a temp file in the same directory, then atomically replace —
        # a crash or a concurrent reader never observes a partially-written file.
        tmp_path = path.with_suffix(f"{path.suffix}.tmp-{os.getpid()}")
        tmp_path.write_text(consensus.model_dump_json())
        os.replace(tmp_path, path)

    def _is_expired(self, consensus: AnalystConsensus) -> bool:
        as_of = consensus.as_of
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - as_of >= self._ttl


def _load(path: Path) -> AnalystConsensus | None:
    """Read a cached entry, treating a corrupt file as a miss rather than a crash."""
    try:
        return AnalystConsensus.model_validate_json(path.read_text())
    except ValueError:
        return None
