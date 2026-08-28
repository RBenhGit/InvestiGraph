"""Growth-rate clamp band applied before any valuation formula uses a growth rate."""

from __future__ import annotations

#: Floor of the growth-rate clamp band. There is no ceiling: the band was
#: `[-5%, 25%]` until the `25%` cap was deliberately removed at the user's
#: request, so this is the only bound left.
GROWTH_RATE_FLOOR_PERCENT: float = -5


def clamp_growth_rate(growth_rate_percent: float) -> float:
    """Clamp a raw growth-rate percentage into the band used by all valuation formulas."""
    return max(GROWTH_RATE_FLOOR_PERCENT, growth_rate_percent)
