from pydantic import BaseModel

from financial_charts.sources.base import Capability, DataSource
from financial_charts.sources.ranges import approx_years, range_years
from financial_charts.template.models import (
    CompanyFundamentals,
    Currency,
    Market,
    Money,
    Period,
)

# A TASE price above this looks like raw agorot that was never divided into shekels.
_AGOROT_NOT_CONVERTED_THRESHOLD = 100_000

# No real operating company's annual revenue is this small — a TASE revenue figure
# below it looks like the "millions of shekels" half of the unit trap: a source that
# reports statement figures pre-scaled (thousands/millions) that never got multiplied
# back up to raw shekels.
_TASE_REVENUE_TOO_SMALL_THRESHOLD = 100_000

# price's point count reflects the requested --range, not the source's true max
# depth (see both adapters' `fetch()` comments on this) — statement endpoints
# return whatever depth the API gives regardless of range, so only those are a
# fair comparison against a declared `max_history`.
_RANGE_BOUNDED_METRICS = {"price"}


class ReconciliationReport(BaseModel):
    missing_metrics: list[str]
    undeclared_extras: list[str]
    unit_warnings: list[str]
    history_points: dict[str, int]
    history_warnings: list[str]

    @property
    def has_mismatch(self) -> bool:
        return (
            bool(self.missing_metrics)
            or bool(self.unit_warnings)
            or bool(self.history_warnings)
        )


def reconcile(
    adapter: DataSource, ticker: str, market: Market, period: Period, range: str
) -> ReconciliationReport:
    """Live-fetch `ticker` and compare the response against the adapter's declared `Capability`.

    Dev-time only — invoked by the `verify-source` CLI, never by a normal render.
    """
    capability = adapter.capability()
    fundamentals = adapter.fetch(ticker, market, period, range)

    declared = capability.metrics
    returned_available = {
        metric_id
        for metric_id, series in fundamentals.series.items()
        if series.available
    }
    returned_all = set(fundamentals.series.keys())

    missing_metrics = sorted(declared - returned_available)
    undeclared_extras = sorted(returned_all - declared)
    unit_warnings = _unit_warnings(market, fundamentals)
    history_points = {
        metric_id: len(series.points)
        for metric_id, series in fundamentals.series.items()
    }
    history_warnings = _history_warnings(capability, period, range, fundamentals)

    return ReconciliationReport(
        missing_metrics=missing_metrics,
        undeclared_extras=undeclared_extras,
        unit_warnings=unit_warnings,
        history_points=history_points,
        history_warnings=history_warnings,
    )


def _history_warnings(
    capability: Capability,
    period: Period,
    range: str,
    fundamentals: CompanyFundamentals,
) -> list[str]:
    """Flag a metric whose actual returned depth falls short of the declared `max_history`.

    Only meaningful when this reconciliation run requested at least as much
    range as is declared — a smaller `--range` legitimately returns less than
    the declared ceiling, so comparing then would be a false positive, not a
    real gap in the declaration.
    """
    declared_years = capability.max_history.get(period)
    requested_years = range_years(range)
    if declared_years is None or requested_years is None:
        return []
    if requested_years < declared_years:
        return []

    warnings = []
    for metric_id, series in fundamentals.series.items():
        if metric_id in _RANGE_BOUNDED_METRICS or not series.available:
            continue
        actual_years = approx_years(period, len(series.points))
        if actual_years < declared_years:
            warnings.append(
                f"{metric_id}: declared {declared_years}y history for {period.value} "
                f"but only ~{actual_years}y returned"
            )
    return warnings


def _unit_warnings(market: Market, fundamentals: CompanyFundamentals) -> list[str]:
    warnings: list[str] = []
    if market != Market.TASE:
        return warnings

    price = fundamentals.series.get("price")
    if price and price.available and price.points:
        last_price = price.points[-1].value
        if last_price.value > _AGOROT_NOT_CONVERTED_THRESHOLD:
            warnings.append(
                f"TASE price {last_price.value} looks like unconverted agorot "
                "(expected shekels after /100 conversion)"
            )

    # The other half of the TASE unit trap: financial-statement figures, not
    # just price. Scoped to `revenue` and to ILS-denominated statements only —
    # a dual-currency company (e.g. Teva: ILS price, USD statements) legitimately
    # has non-ILS statement figures this check must not apply to.
    revenue = fundamentals.series.get("revenue")
    if revenue and revenue.available and revenue.points:
        last_revenue = revenue.points[-1].value
        if (
            isinstance(last_revenue, Money)
            and last_revenue.currency == Currency.ILS
            and 0 <= last_revenue.as_base_units() < _TASE_REVENUE_TOO_SMALL_THRESHOLD
        ):
            warnings.append(
                f"TASE revenue {last_revenue.as_base_units():.0f} ILS looks implausibly "
                "small for an operating company — check whether the source's statement "
                "figures need scaling up (the millions-of-shekels half of the TASE unit trap)"
            )

    return warnings
