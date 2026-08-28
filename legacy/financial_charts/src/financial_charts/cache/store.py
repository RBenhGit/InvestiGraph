import os
from datetime import date
from pathlib import Path

from financial_charts.template.models import CompanyFundamentals, Period

_DEFAULT_CACHE_DIR = Path(".cache") / "financial_charts"


def _key(ticker: str, source: str, period: Period, range: str, as_of: date) -> str:
    return (
        f"{ticker.upper()}_{source}_{period.value}_{range.lower()}_{as_of.isoformat()}"
    )


class TemplateCache:
    """Disk cache for fetched `CompanyFundamentals`, keyed by (ticker, source, period, range, date).

    Paid sources are metered, so the display reads cache-first before ever calling an adapter.
    """

    def __init__(self, cache_dir: Path | str = _DEFAULT_CACHE_DIR):
        self._dir = Path(cache_dir)

    def _path(
        self, ticker: str, source: str, period: Period, range: str, as_of: date
    ) -> Path:
        return self._dir / f"{_key(ticker, source, period, range, as_of)}.json"

    def get(
        self, ticker: str, source: str, period: Period, range: str, as_of: date
    ) -> CompanyFundamentals | None:
        path = self._path(ticker, source, period, range, as_of)
        if not path.exists():
            return None
        return _load(path)

    def latest(
        self, ticker: str, source: str, period: Period, range: str
    ) -> CompanyFundamentals | None:
        """Most recent cached entry for (ticker, source, period, range), any date.

        Used to serve a stale-but-usable page when a live fetch fails.
        """
        prefix = f"{ticker.upper()}_{source}_{period.value}_{range.lower()}_"
        matches = (
            sorted(self._dir.glob(f"{prefix}*.json")) if self._dir.exists() else []
        )
        # Newest-dated file first; a corrupt entry falls back to the next most
        # recent readable one rather than treating the whole lookup as a miss.
        for path in reversed(matches):
            fundamentals = _load(path)
            if fundamentals is not None:
                return fundamentals
        return None

    def put(
        self,
        ticker: str,
        source: str,
        period: Period,
        range: str,
        as_of: date,
        fundamentals: CompanyFundamentals,
    ) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._path(ticker, source, period, range, as_of)
        # Write to a temp file in the same directory, then atomically replace —
        # a crash or a concurrent reader never observes a partially-written file.
        tmp_path = path.with_suffix(f"{path.suffix}.tmp-{os.getpid()}")
        tmp_path.write_text(fundamentals.model_dump_json())
        os.replace(tmp_path, path)


def _load(path: Path) -> CompanyFundamentals | None:
    """Read a cached entry, treating a corrupt file as a miss rather than a crash."""
    try:
        return CompanyFundamentals.model_validate_json(path.read_text())
    except ValueError:
        return None
