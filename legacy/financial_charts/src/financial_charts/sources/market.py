import re

from financial_charts.template.models import Market

_VALID_TICKER = re.compile(r"^[A-Za-z0-9.\-]+$")


def market_of(ticker: str) -> Market:
    """Route a ticker to its market by the `.TA` suffix (TASE); bare tickers are US."""
    if ticker.upper().endswith(".TA"):
        return Market.TASE
    return Market.US


def is_valid_ticker(ticker: str) -> bool:
    """Whether `ticker` is a plausible ticker string.

    A real-world guard, not a market-data one: `ticker` flows into cache/output
    file paths (see cache/store.py), so this rejects path separators and other
    characters that have no business in a ticker before they ever reach the
    filesystem.
    """
    return bool(ticker) and bool(_VALID_TICKER.match(ticker))


def normalize_ticker(ticker: str) -> str:
    """Canonical uppercase form of a validated ticker.

    Callers should apply this once, right after `is_valid_ticker`, so every
    downstream consumer (adapters' own `.TA`-suffix stripping, cache keys,
    output filenames) sees one consistent case rather than each having to
    re-normalize independently.
    """
    return ticker.strip().upper()
