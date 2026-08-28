"""The closed `ValuationResult` union shared by every valuation formula.

Errors are returned, never raised: a formula either succeeds (`ValuationOk`,
carrying the fair value plus the inputs actually used) or fails
(`ValuationErr`, carrying one `ValuationError` code) — never an exception.
Both the web and CLI layers depend on this exact shape.
"""

from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict


class ValuationInputsUsed(BaseModel):
    """Inputs a formula actually used, echoed back in the result for display."""

    model_config = ConfigDict(frozen=True)

    eps_ttm: float
    growth_rate_percent_raw: float
    growth_rate_percent_clamped: float


ValuationError = Literal[
    "MISSING_EPS",
    "NEGATIVE_OR_ZERO_EPS",
    "MISSING_GROWTH_RATE",
    # Lynch only: `EPS x growth%` is only meaningful for positive growth. A
    # non-positive rate yields a zero or NEGATIVE dollar figure, which is not
    # a low valuation but a meaningless one.
    "NEGATIVE_GROWTH_RATE",
    "INVALID_EXIT_PE",
    "INVALID_REQUIRED_RETURN",
    "INVALID_YEARS",
    "INVALID_MOS",
]

TInputs = TypeVar("TInputs", bound=ValuationInputsUsed)


class ValuationOk(BaseModel, Generic[TInputs]):
    model_config = ConfigDict(frozen=True)

    ok: Literal[True] = True
    fair_value: float
    inputs: TInputs
    intermediate: dict[str, float] | None = None


class ValuationErr(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: Literal[False] = False
    error: ValuationError


ValuationResult = ValuationOk[TInputs] | ValuationErr
