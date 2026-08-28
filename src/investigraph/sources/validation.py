from financial_charts.sources.base import Capability, UnsupportedPeriod
from financial_charts.sources.ranges import range_years
from financial_charts.template.models import Market, Period


def require_supported_period(capability: Capability, period: Period) -> None:
    """Raise `UnsupportedPeriod` before a fetch, rather than letting an adapter
    silently mistreat an unsupported period as one it does support (e.g.
    yfinance treating a TTM request as quarterly).

    `check_request` also flags an unsupported period, but only as an advisory
    limit computed *after* a successful fetch — this is a separate, additive
    pre-fetch gate for the one case where fetching under the wrong period
    would return data mislabeled as something it isn't.
    """
    if period not in capability.periods:
        raise UnsupportedPeriod(f"source does not support period {period.value}")


def check_request(
    capability: Capability, market: Market, period: Period, range: str
) -> list[str]:
    """Compare a declared `Capability` against a requested (market, period, range).

    Pure, offline, deterministic. Returns human-readable limits to surface as
    `source_limits` on the rendered page; an empty list means the request is
    fully covered by the declared capability.
    """
    limits: list[str] = []

    if market not in capability.markets:
        limits.append(f"source does not support market {market.value}")

    if period not in capability.periods:
        limits.append(f"source does not support period {period.value}")
        return limits

    requested_years = range_years(range)
    if requested_years is None:
        limits.append(f"unrecognized range {range!r}")
        return limits

    max_years = capability.max_history.get(period)
    if max_years is not None and requested_years > max_years:
        limits.append(
            f"requested range {range} exceeds source's {max_years}y history for {period.value}"
        )

    return limits
