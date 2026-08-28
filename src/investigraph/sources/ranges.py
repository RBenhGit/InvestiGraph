"""The canonical `--range`/`range=` vocabulary, shared by validation, the web
picker, and both adapters (each of which also keeps its own range -> API-token
mapping — a different concern from this shared vocabulary/years table).
"""

from financial_charts.template.models import Period

RANGES: tuple[str, ...] = ("6m", "1y", "3y", "5y", "10y", "max")

_RANGE_YEARS: dict[str, int] = {
    "6m": 1,
    "1y": 1,
    "3y": 3,
    "5y": 5,
    "10y": 10,
    "max": 10_000,
}


def range_years(range_: str) -> int | None:
    """Years spanned by a range string, or `None` if it's not in `RANGES`."""
    return _RANGE_YEARS.get(range_.lower())


def approx_years(period: Period, point_count: int) -> int:
    """Approximate years of history represented by `point_count` points at `period`'s cadence.

    Shared by dev-time tooling only (`commission-source`, `verify-source`) to
    compare an adapter's actual returned depth against a declared/derived
    `Capability` — never on the render path, which trusts the declaration
    outright.
    """
    if period == Period.ANNUAL:
        return max(point_count, 0)
    if period == Period.QUARTERLY:
        return max(point_count // 4, 0)
    raise ValueError(f"cannot approximate history depth for period {period.value}")
