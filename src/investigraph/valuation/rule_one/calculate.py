"""Method B (Rule #1-style): project EPS forward, apply an exit P/E, discount back."""

from __future__ import annotations

import math

from pydantic import ConfigDict

from investigraph.valuation.shared.clamp import clamp_growth_rate
from investigraph.valuation.shared.types import (
    ValuationErr,
    ValuationInputsUsed,
    ValuationOk,
)


class RuleOneInputsUsed(ValuationInputsUsed):
    """`ValuationInputsUsed` plus the Rule #1-specific assumptions."""

    model_config = ConfigDict(frozen=True)

    exit_pe_multiple: float
    required_return_percent: float
    years: int
    mos_percent: float


def calculate_rule_one_value(
    eps_ttm: float | None,
    growth_rate_percent: float | None,
    exit_pe_multiple: float | None,
    required_return_percent: float | None,
    years: int | float | None,
    mos_percent: float | None = 0,
) -> ValuationOk[RuleOneInputsUsed] | ValuationErr:
    """Project EPS forward `years` at the (clamped) growth rate, apply an exit
    P/E multiple, discount back at `required_return_percent`.

    An optional `mos_percent` (Margin of Safety, e.g. 25 for 25%, defaults to
    0) discounts the sticker price down to the target buy price
    (`fair_value = sticker_price * (1 - mos_percent / 100)`).

    A non-positive growth rate is not rejected here: compounding a positive
    EPS at a negative rate shrinks it without ever flipping the sign, so the
    result stays meaningful.

    `exit_pe_multiple`, `required_return_percent`, `years`, and `mos_percent`
    all accept `None` (not just the original TS's `undefined`) because
    `history/models.py`'s `SavedValuation`/`ScenarioValuation` model every one
    of them as optional -- a route re-valuing a saved record must get a typed
    `INVALID_*`/graceful-default result here, not a `TypeError`. `years` also
    accepts a whole-number `float` (e.g. `10.0`), because Pydantic coerces an
    int assigned to `SavedValuation.years: float | None` on save/reload; the
    original's `Number.isInteger(years)` already treated `10.0` and `10` as
    the same value (JS has one number type), so this isn't a behavior change
    from the original, only from a too-literal first port of it.
    """
    if eps_ttm is None or math.isnan(eps_ttm):
        return ValuationErr(error="MISSING_EPS")
    if eps_ttm <= 0:
        return ValuationErr(error="NEGATIVE_OR_ZERO_EPS")
    if growth_rate_percent is None or math.isnan(growth_rate_percent):
        return ValuationErr(error="MISSING_GROWTH_RATE")
    if exit_pe_multiple is None or not (exit_pe_multiple > 0):
        return ValuationErr(error="INVALID_EXIT_PE")
    if required_return_percent is None or not (required_return_percent > 0):
        return ValuationErr(error="INVALID_REQUIRED_RETURN")
    if (
        years is None
        or isinstance(years, bool)
        or not isinstance(years, (int, float))
        or (isinstance(years, float) and not years.is_integer())
        or years <= 0
    ):
        return ValuationErr(error="INVALID_YEARS")
    years = int(years)
    # `None` means "omitted" here, same as the original's `undefined` default-parameter
    # substitution -- both mean "no MoS", not "invalid MoS".
    mos_percent = 0.0 if mos_percent is None else mos_percent
    if math.isnan(mos_percent) or mos_percent < 0 or mos_percent >= 100:
        return ValuationErr(error="INVALID_MOS")

    growth_rate_percent_clamped = clamp_growth_rate(growth_rate_percent)
    g = growth_rate_percent_clamped / 100
    r = required_return_percent / 100
    eps_future = eps_ttm * (1 + g) ** years
    future_price = eps_future * exit_pe_multiple
    sticker_price = future_price / (1 + r) ** years
    fair_value = (
        sticker_price * (1 - mos_percent / 100) if mos_percent > 0 else sticker_price
    )

    return ValuationOk(
        fair_value=fair_value,
        inputs=RuleOneInputsUsed(
            eps_ttm=eps_ttm,
            growth_rate_percent_raw=growth_rate_percent,
            growth_rate_percent_clamped=growth_rate_percent_clamped,
            exit_pe_multiple=exit_pe_multiple,
            required_return_percent=required_return_percent,
            years=years,
            mos_percent=mos_percent,
        ),
        intermediate={
            "eps_future": eps_future,
            "future_price": future_price,
            "sticker_price": sticker_price,
            "mos_price": fair_value,
        },
    )
