from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict, model_validator


class Currency(str, Enum):
    USD = "USD"
    ILS = "ILS"


class Unit(str, Enum):
    ONES = "ones"
    THOUSANDS = "thousands"
    MILLIONS = "millions"


_UNIT_SCALE: dict[Unit, int] = {
    Unit.ONES: 1,
    Unit.THOUSANDS: 1_000,
    Unit.MILLIONS: 1_000_000,
}


class Period(str, Enum):
    QUARTERLY = "quarterly"
    TTM = "ttm"
    ANNUAL = "annual"


class Market(str, Enum):
    US = "US"
    TASE = "TASE"


class Money(BaseModel):
    """A monetary value tagged with its currency and unit scale.

    Two `Money` values in different currencies or scales must never be combined
    silently (e.g. TASE prices in agorot vs. statements in millions of shekels).
    """

    model_config = ConfigDict(frozen=True)

    value: float
    currency: Currency
    scale: Unit

    def to(self, scale: Unit) -> Money:
        """Rescale to a different unit, preserving the represented amount."""
        base = self.value * _UNIT_SCALE[self.scale]
        return Money(
            value=base / _UNIT_SCALE[scale], currency=self.currency, scale=scale
        )

    def require_same_currency(self, other: Money) -> None:
        """Raise if `other` isn't in this Money's currency.

        Two `Money` values in different currencies must never be combined or
        compared silently — this is the one shared guard for that, used by
        `__add__`/`__sub__` here and by `derived.ratio()`.
        """
        if self.currency != other.currency:
            raise ValueError(
                f"cannot combine Money of different currencies: {self.currency} vs {other.currency}"
            )

    def __add__(self, other: Money) -> Money:
        self.require_same_currency(other)
        other_rescaled = other.to(self.scale)
        return Money(
            value=self.value + other_rescaled.value,
            currency=self.currency,
            scale=self.scale,
        )

    def __sub__(self, other: Money) -> Money:
        self.require_same_currency(other)
        other_rescaled = other.to(self.scale)
        return Money(
            value=self.value - other_rescaled.value,
            currency=self.currency,
            scale=self.scale,
        )

    def as_base_units(self) -> float:
        """The represented amount in the currency's smallest common unit (ones)."""
        return self.value * _UNIT_SCALE[self.scale]


class Point(BaseModel):
    date: date
    value: Money | float


class MetricSeries(BaseModel):
    metric_id: str
    points: list[Point] = []
    available: bool = True

    @model_validator(mode="after")
    def _empty_points_are_unavailable(self) -> MetricSeries:
        """A series with no points is never `available` — normalize it at the
        boundary rather than trusting every producer to set both fields by hand.
        """
        if not self.points:
            self.available = False
        return self

    @model_validator(mode="after")
    def _consistent_money_tagging(self) -> MetricSeries:
        """Every `Money` point in one series must share a currency and scale.

        A mismatch here is an adapter bug (e.g. the TASE agorot-vs-millions
        trap), not a runtime surprise a chart should have to defend against —
        fail loud at construction instead of silently mis-plotting.
        """
        money_points = [p.value for p in self.points if isinstance(p.value, Money)]
        if money_points:
            currencies = {m.currency for m in money_points}
            scales = {m.scale for m in money_points}
            if len(currencies) > 1 or len(scales) > 1:
                raise ValueError(
                    f"{self.metric_id}: inconsistent Money currency/scale across points "
                    f"(currencies={currencies}, scales={scales})"
                )
        return self


class CompanyFundamentals(BaseModel):
    """`currency` is the market's native trading currency (₪ for TASE, $ for
    US) — it labels `price`, not necessarily every series. A dual-listed
    company can legitimately report its financial statements in a different
    currency than the one its shares trade in (e.g. a TASE-listed multinational
    filing in USD while its price quotes in ILS): `MetricSeries`'s own
    consistency check keeps *each* series internally coherent, but no field
    here forces every series to match `currency` — that would reject real,
    correctly-tagged data.
    """

    ticker: str
    market: Market
    currency: Currency
    period: Period
    range: str
    series: dict[str, MetricSeries] = {}
    source_limits: list[str] = []
