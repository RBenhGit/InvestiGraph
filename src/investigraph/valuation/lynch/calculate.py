"""Method A (Lynch/PEG-style): `fair_value = eps_ttm * growth_rate_percent`, no discounting."""

from __future__ import annotations

import math

from investigraph.valuation.shared.clamp import clamp_growth_rate
from investigraph.valuation.shared.types import (
    ValuationErr,
    ValuationInputsUsed,
    ValuationOk,
)


def calculate_lynch_value(
    eps_ttm: float | None,
    growth_rate_percent: float | None,
) -> ValuationOk[ValuationInputsUsed] | ValuationErr:
    """Compute the Lynch/PEG-style fair value.

    `eps_ttm` and `growth_rate_percent` accept `None` because they flow in
    directly from independently-nullable upstream fields (e.g. an analyst
    growth estimate) — this function is what turns that absence into
    `MISSING_EPS` / `MISSING_GROWTH_RATE` rather than pushing a null-check
    onto every caller.
    """
    if eps_ttm is None or math.isnan(eps_ttm):
        return ValuationErr(error="MISSING_EPS")
    if eps_ttm <= 0:
        return ValuationErr(error="NEGATIVE_OR_ZERO_EPS")
    if growth_rate_percent is None or math.isnan(growth_rate_percent):
        return ValuationErr(error="MISSING_GROWTH_RATE")

    # `EPS x growth%` is a PEG-style heuristic defined only for a growing
    # company. With a non-positive rate it returns 0 or a negative dollar
    # amount -- e.g. ABBV's real -29.03% 3y CAGR (clamped to -5%) gave a "fair
    # value" of -17.69, which the CLI and the web UI both rendered as a
    # legitimate number with a -108% "downside". That is not a cheap stock,
    # it is an inapplicable formula, so it must surface as an error. Rule #1
    # is unaffected: compounding a positive EPS at a negative rate shrinks it
    # without flipping the sign.
    if growth_rate_percent <= 0:
        return ValuationErr(error="NEGATIVE_GROWTH_RATE")

    growth_rate_percent_clamped = clamp_growth_rate(growth_rate_percent)
    fair_value = eps_ttm * growth_rate_percent_clamped

    return ValuationOk(
        fair_value=fair_value,
        inputs=ValuationInputsUsed(
            eps_ttm=eps_ttm,
            growth_rate_percent_raw=growth_rate_percent,
            growth_rate_percent_clamped=growth_rate_percent_clamped,
        ),
    )
