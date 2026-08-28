from typing import NamedTuple

from financial_charts.sources.base import Capability, DataSource
from financial_charts.sources.twelvedata.adapter import TwelveDataAdapter
from financial_charts.sources.twelvedata.capability import (
    CAPABILITY as _TWELVEDATA_CAPABILITY,
)
from financial_charts.sources.yfinance.adapter import YFinanceAdapter
from financial_charts.sources.yfinance.capability import (
    CAPABILITY as _YFINANCE_CAPABILITY,
)


class _Registration(NamedTuple):
    adapter_cls: type[DataSource]
    capability: Capability


_SOURCES: dict[str, _Registration] = {
    "yfinance": _Registration(YFinanceAdapter, _YFINANCE_CAPABILITY),
    "twelvedata": _Registration(TwelveDataAdapter, _TWELVEDATA_CAPABILITY),
}


def _lookup(name: str) -> _Registration:
    try:
        return _SOURCES[name]
    except KeyError:
        raise KeyError(
            f"unknown data source {name!r}; registered sources: {sorted(_SOURCES)}"
        ) from None


def get_source(name: str) -> DataSource:
    """Resolve a `DATA_SOURCE` name to an adapter instance.

    Raises `KeyError` for an unregistered name; a paid adapter with no
    credentials raises `MissingCredentials` from its own constructor.
    """
    return _lookup(name).adapter_cls()


def get_capability(name: str) -> Capability:
    """Look up a registered source's declared `Capability`.

    Reads the static `capability.py` declaration directly — no adapter is
    constructed, so this needs no credentials and makes no network call.
    """
    return _lookup(name).capability


def registered_sources() -> list[str]:
    return sorted(_SOURCES)
