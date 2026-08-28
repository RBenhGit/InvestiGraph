"""`AnalystConsensus` — the published shape this module returns.

Ported from Eps_Evaluation's `AnalystConsensus`/`AnalystPriceTarget`
(legacy/eps_evaluation/src/data/yahoo/types.ts). This is not a `CompanyFundamentals`
and this module is not a `DataSource` (see `sources/base.py`) — see `adapter.py`'s
module docstring for why.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class AnalystPriceTarget(BaseModel):
    model_config = ConfigDict(frozen=True)

    mean: float | None = None
    high: float | None = None
    low: float | None = None
    number_of_analysts: int | None = None


class AnalystConsensus(BaseModel):
    """Yahoo-sourced analyst consensus data for one ticker.

    Every field is independently nullable — thin analyst coverage (a young IPO,
    an ETF, a foreign-listed company) or a per-ticker gap in Yahoo's own data
    must degrade that one field to `None`, never the whole lookup (see
    `adapter.py`'s field-mapping table for what backs each field).

    `trailing_eps` and `most_recent_quarter_end_date` are an independent
    cross-check/fallback source for the template's own TTM EPS, consumed by
    `valuation/resolve_eps.py` — never shown to the user as if it came from
    Twelve Data (see that module's `EpsSource` labels).
    """

    model_config = ConfigDict(frozen=True)

    ticker: str
    # NOT a source for valuation/growth.py's `analyst_estimate_5y_percent` slot in the
    # CLI/web growth fallback chain -- different horizon (+1y here, vs. the chain's 5y),
    # and originally strictly separate (the chain used Twelve Data's growth_estimates.
    # next_5_years_pa; this field was display-only, see legacy/eps_evaluation/src/web/
    # public/app.js's analyst table). Wiring this in would silently change every fair
    # value, and the CLI/web parity check wouldn't catch it since both would drift
    # together -- keep this display-only.
    next_year_eps_growth_percent: float | None = None
    price_target: AnalystPriceTarget
    recommendation_key: str | None = None
    beta: float | None = None
    price_to_sales: float | None = None
    rule_of_40: float | None = None
    trailing_eps: float | None = None
    most_recent_quarter_end_date: date | None = None
    as_of: datetime
