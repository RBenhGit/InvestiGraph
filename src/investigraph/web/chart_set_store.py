import json
import os
from pathlib import Path

_DEFAULT_STORE_DIR = Path(".cache") / "financial_charts"
_FILENAME = "chart_sets.json"


class ChartSetStore:
    """Disk-persisted user-created chart sets, keyed by name -> chart id list.

    Mirrors `cache/store.py`'s `TemplateCache`: atomic write (temp file then
    `os.replace`), missing or corrupt file treated as empty rather than a crash.
    """

    def __init__(self, store_dir: Path | str = _DEFAULT_STORE_DIR):
        self._path = Path(store_dir) / _FILENAME

    def load(self) -> dict[str, list[str]]:
        if not self._path.exists():
            return {}
        try:
            data = json.loads(self._path.read_text())
        except ValueError:
            return {}
        if not isinstance(data, dict):
            return {}
        # A single malformed entry (wrong shape, e.g. from a hand edit or a
        # future schema change) degrades to being dropped, not a crash for
        # the whole store — same posture as cache/store.py's corrupt-entry
        # handling in `latest()`.
        return {
            name: chart_ids
            for name, chart_ids in data.items()
            if isinstance(chart_ids, list)
            and all(isinstance(c, str) for c in chart_ids)
        }

    def save(self, name: str, chart_ids: list[str]) -> None:
        data = self.load()
        data[name] = chart_ids
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path.with_suffix(f"{self._path.suffix}.tmp-{os.getpid()}")
        tmp_path.write_text(json.dumps(data))
        os.replace(tmp_path, self._path)
