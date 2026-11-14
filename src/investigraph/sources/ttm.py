"""Build a `Period.TTM` `CompanyFundamentals` from the QUARTERLY and ANNUAL series.

TTM is never fetched natively (see `template/trailing.py`'s `derive_ttm_fundamentals`): it is
derived from one QUARTERLY series plus, when useful, the matching ANNUAL one (to reconstruct a
quarter the source omits and to extend the history with fiscal-year-end points).

The point of this module is that it does **not** fetch anything itself: the caller supplies
`fetch_period`, so *where* those two series come from stays the caller's decision. An adapter
passes a fetch that goes back through itself; the web and CLI loaders pass their cache-aware
fetch, so a page whose other charts already loaded QUARTERLY and ANNUAL pays nothing extra for
its TTM charts — and cannot disagree with them about the data. One composition, used by all
of them, so TTM is built the same way everywhere.
"""

from __future__ import annotations

from typing import Callable

from investigraph.sources.base import SourceUnavailable
from investigraph.template.models import CompanyFundamentals, Period
from investigraph.template.trailing import derive_ttm_fundamentals


def build_ttm_fundamentals(
    fetch_period: Callable[[Period], CompanyFundamentals],
) -> CompanyFundamentals:
    """`Period.TTM` fundamentals built from `fetch_period(QUARTERLY)` and `fetch_period(ANNUAL)`.

    A failure fetching QUARTERLY propagates (there is no TTM without it). A failure fetching
    ANNUAL (`SourceUnavailable`, e.g. out of API credits) degrades to a quarterly-only TTM:
    `derive_ttm_fundamentals` then says in `source_limits` that a missing quarter could not be
    reconstructed, rather than the whole page failing. The annual series is requested lazily,
    once, and only as far as `derive_ttm_fundamentals` needs it.
    """
    quarterly = fetch_period(Period.QUARTERLY)

    def annual_loader() -> CompanyFundamentals | None:
        try:
            return fetch_period(Period.ANNUAL)
        except SourceUnavailable:
            return None

    return derive_ttm_fundamentals(quarterly, annual_loader=annual_loader)
