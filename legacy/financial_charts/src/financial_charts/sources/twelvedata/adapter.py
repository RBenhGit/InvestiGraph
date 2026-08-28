import os

import requests
from dotenv import load_dotenv

from financial_charts.sources.base import (
    Capability,
    MissingCredentials,
    SourceUnavailable,
    TickerNotFound,
)
from financial_charts.sources.currency import AGOROT_CODE, map_currency
from financial_charts.sources.twelvedata.capability import CAPABILITY
from financial_charts.template.models import (
    CompanyFundamentals,
    Currency,
    Market,
    MetricSeries,
    Money,
    Period,
    Point,
    Unit,
)

_BASE_URL = "https://api.twelvedata.com"

# Daily bars at every range, roughly 260 per year of the requested window.
#
# The price chart's SMA overlays count *points*, not days (see charts/builtins/price.py),
# so a source that returned weekly or monthly bars for long ranges would silently turn
# "SMA 50" into a 50-week or 50-month average — and yfinance, which is always daily,
# would disagree with this source on the same chart. Every range therefore asks for
# daily bars, matching yfinance's cadence.
#
# `outputsize` costs nothing extra: Twelve Data bills `time_series` per request, not per
# point, and caps the parameter at 5000 (verified against the live API).
_PRICE_INTERVAL = "1day"
_PRICE_OUTPUTSIZE_BY_RANGE = {
    "6m": 130,
    "1y": 260,
    "3y": 780,
    "5y": 1300,
    "10y": 2600,
    "max": 5000,
}


class TwelveDataAdapter:
    def __init__(self, api_key: str | None = None):
        load_dotenv()
        self._api_key = api_key or os.environ.get("TWELVEDATA_API_KEY")
        if not self._api_key:
            raise MissingCredentials("TWELVEDATA_API_KEY is not set")

    def capability(self) -> Capability:
        return CAPABILITY

    def fetch(
        self, ticker: str, market: Market, period: Period, range: str
    ) -> CompanyFundamentals:
        symbol = ticker.removesuffix(".TA") if market == Market.TASE else ticker
        mic_code = "XTAE" if market == Market.TASE else None

        # `range` only bounds this price fetch (via `_price_params`'s
        # `outputsize`); the income_statement/cash_flow endpoints below take no
        # range/date param, so they return whatever depth Twelve Data gives.
        price_json = self._get(
            "time_series", symbol=symbol, mic_code=mic_code, **_price_params(range)
        )
        income_json = self._get(
            "income_statement", symbol=symbol, mic_code=mic_code, period=period.value
        )
        cashflow_json = self._get(
            "cash_flow", symbol=symbol, mic_code=mic_code, period=period.value
        )
        balance_sheet_json = self._get(
            "balance_sheet", symbol=symbol, mic_code=mic_code, period=period.value
        )

        display_currency = Currency.ILS if market == Market.TASE else Currency.USD
        source_limits: list[str] = []

        series: dict[str, MetricSeries] = {
            "price": _price_series(price_json, source_limits),
        }
        income_statement = income_json.get("income_statement", [])
        cashflow_statement = cashflow_json.get("cash_flow", [])
        financial_currency = map_currency(income_json.get("meta", {}).get("currency"))

        series["revenue"] = _income_series(
            income_statement, "sales", financial_currency, "revenue", source_limits
        )
        series["net_income"] = _income_series(
            income_statement,
            "net_income",
            financial_currency,
            "net_income",
            source_limits,
        )
        series["eps"] = _income_series(
            income_statement, "eps_diluted", financial_currency, "eps", source_limits
        )
        series["free_cash_flow"] = _cashflow_series(
            cashflow_statement, financial_currency, source_limits
        )
        series["gross_margin"] = _margin_series(
            income_statement, "gross_profit", "sales", "gross_margin", source_limits
        )
        series["net_margin"] = _margin_series(
            income_statement, "net_income", "sales", "net_margin", source_limits
        )
        series["ebitda"] = _income_series(
            income_statement, "ebitda", financial_currency, "ebitda", source_limits
        )
        series["research_and_development"] = _income_series(
            income_statement,
            ("operating_expense", "research_and_development"),
            financial_currency,
            "research_and_development",
            source_limits,
        )
        series["selling_general_administrative"] = _income_series(
            income_statement,
            ("operating_expense", "selling_general_and_administrative"),
            financial_currency,
            "selling_general_administrative",
            source_limits,
        )
        series["shares_outstanding"] = _income_float_series(
            income_statement,
            "diluted_shares_outstanding",
            "shares_outstanding",
            source_limits,
        )
        series["dividends_paid"] = _income_series(
            cashflow_statement,
            ("financing_activities", "common_dividends"),
            financial_currency,
            "dividends_paid",
            source_limits,
            absolute=True,
        )
        series["ebit"] = _income_series(
            income_statement, "ebit", financial_currency, "ebit", source_limits
        )

        balance_sheet_statement = balance_sheet_json.get("balance_sheet", [])
        series["total_assets"] = _income_series(
            balance_sheet_statement,
            ("assets", "total_assets"),
            financial_currency,
            "total_assets",
            source_limits,
        )
        series["total_liabilities"] = _income_series(
            balance_sheet_statement,
            ("liabilities", "total_liabilities"),
            financial_currency,
            "total_liabilities",
            source_limits,
        )
        series["total_equity"] = _income_series(
            balance_sheet_statement,
            ("shareholders_equity", "total_shareholders_equity"),
            financial_currency,
            "total_equity",
            source_limits,
        )
        series["cash_and_equivalents"] = _income_series(
            balance_sheet_statement,
            ("assets", "current_assets", "cash_and_cash_equivalents"),
            financial_currency,
            "cash_and_equivalents",
            source_limits,
        )
        series["total_current_assets"] = _income_series(
            balance_sheet_statement,
            ("assets", "current_assets", "total_current_assets"),
            financial_currency,
            "total_current_assets",
            source_limits,
        )
        series["total_current_liabilities"] = _income_series(
            balance_sheet_statement,
            ("liabilities", "current_liabilities", "total_current_liabilities"),
            financial_currency,
            "total_current_liabilities",
            source_limits,
        )
        series["total_debt"] = _total_debt_series(
            balance_sheet_statement, financial_currency, source_limits
        )

        return CompanyFundamentals(
            ticker=ticker,
            market=market,
            currency=display_currency,
            period=period,
            range=range,
            series=series,
            source_limits=source_limits,
        )

    def _get(self, endpoint: str, **params) -> dict:
        query = {k: v for k, v in params.items() if v is not None}
        query["apikey"] = self._api_key
        try:
            response = requests.get(f"{_BASE_URL}/{endpoint}", params=query, timeout=30)
        except requests.RequestException as exc:
            raise SourceUnavailable(f"twelvedata request failed: {exc}") from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise SourceUnavailable(
                f"twelvedata returned a non-JSON response: {response.text[:200]}"
            ) from exc

        if isinstance(payload, dict) and payload.get("status") == "error":
            if payload.get("code") == 404:
                raise TickerNotFound(params.get("symbol", ""))
            raise SourceUnavailable(payload.get("message", "twelvedata request failed"))
        return payload


def _price_params(range: str) -> dict:
    outputsize = _PRICE_OUTPUTSIZE_BY_RANGE.get(range.lower(), 5000)
    return {"interval": _PRICE_INTERVAL, "outputsize": outputsize}


def _unavailable(metric_id: str, source_limits: list[str]) -> MetricSeries:
    """A metric with no usable data for this ticker: note why, and mark it unavailable."""
    source_limits.append(f"{metric_id}: no data available for this ticker")
    return MetricSeries(metric_id=metric_id, points=[], available=False)


def _price_series(price_json: dict, source_limits: list[str]) -> MetricSeries:
    meta = price_json.get("meta", {})
    values = price_json.get("values", [])
    currency = map_currency(meta.get("currency"))
    if not values or currency is None:
        return _unavailable("price", source_limits)

    is_agorot = meta.get("currency") == AGOROT_CODE
    points = [
        Point(
            date=row["datetime"],
            value=Money(
                value=(float(row["close"]) / 100 if is_agorot else float(row["close"])),
                currency=currency,
                scale=Unit.ONES,
            ),
        )
        for row in reversed(values)
        if row.get("datetime") is not None and row.get("close") is not None
    ]
    return MetricSeries(metric_id="price", points=points, available=True)


def _field_value(row: dict, field: str | tuple[str, ...]):
    """Resolve a top-level or dotted-path field (e.g. Twelve Data's nested
    `operating_expense.research_and_development`) from one statement row.
    """
    if isinstance(field, str):
        return row.get(field)
    value = row
    for key in field:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _income_series(
    income_statement: list[dict],
    field: str | tuple[str, ...],
    currency: Currency | None,
    metric_id: str,
    source_limits: list[str],
    absolute: bool = False,
) -> MetricSeries:
    if currency is None:
        return _unavailable(metric_id, source_limits)

    points = []
    for row in reversed(income_statement):
        if row.get("fiscal_date") is None:
            continue
        raw = _field_value(row, field)
        if raw is None:
            continue
        points.append(
            Point(
                date=row["fiscal_date"],
                value=Money(
                    value=abs(float(raw)) if absolute else float(raw),
                    currency=currency,
                    scale=Unit.ONES,
                ),
            )
        )
    if not points:
        return _unavailable(metric_id, source_limits)
    return MetricSeries(metric_id=metric_id, points=points, available=True)


def _total_debt_series(
    balance_sheet_statement: list[dict],
    currency: Currency | None,
    source_limits: list[str],
) -> MetricSeries:
    """Twelve Data's balance sheet has no single `total_debt` field — sum its
    short-term and long-term debt components (whichever are reported).
    """
    if currency is None:
        return _unavailable("total_debt", source_limits)

    points = []
    for row in reversed(balance_sheet_statement):
        if row.get("fiscal_date") is None:
            continue
        liabilities = row.get("liabilities", {})
        short_term = _field_value(
            liabilities, ("current_liabilities", "short_term_debt")
        )
        long_term = _field_value(
            liabilities, ("non_current_liabilities", "long_term_debt")
        )
        if short_term is None and long_term is None:
            continue
        total = (short_term or 0) + (long_term or 0)
        points.append(
            Point(
                date=row["fiscal_date"],
                value=Money(value=float(total), currency=currency, scale=Unit.ONES),
            )
        )
    if not points:
        return _unavailable("total_debt", source_limits)
    return MetricSeries(metric_id="total_debt", points=points, available=True)


def _income_float_series(
    income_statement: list[dict],
    field: str | tuple[str, ...],
    metric_id: str,
    source_limits: list[str],
) -> MetricSeries:
    """Like `_income_series` but for a plain (non-Money) numeric field, e.g. a share count."""
    points = []
    for row in reversed(income_statement):
        if row.get("fiscal_date") is None:
            continue
        raw = _field_value(row, field)
        if raw is None:
            continue
        points.append(Point(date=row["fiscal_date"], value=float(raw)))
    if not points:
        return _unavailable(metric_id, source_limits)
    return MetricSeries(metric_id=metric_id, points=points, available=True)


def _cashflow_series(
    cashflow_statement: list[dict], currency: Currency | None, source_limits: list[str]
) -> MetricSeries:
    if currency is None:
        return _unavailable("free_cash_flow", source_limits)

    points = []
    for row in reversed(cashflow_statement):
        if row.get("fiscal_date") is None:
            continue
        fcf = row.get("free_cash_flow")
        if fcf is None:
            operating = row.get("operating_activities", {}).get("operating_cash_flow")
            capex = row.get("investing_activities", {}).get("capital_expenditures")
            fcf = (
                operating + capex
                if operating is not None and capex is not None
                else None
            )
        if fcf is not None:
            points.append(
                Point(
                    date=row["fiscal_date"],
                    value=Money(value=float(fcf), currency=currency, scale=Unit.ONES),
                )
            )
    if not points:
        return _unavailable("free_cash_flow", source_limits)
    return MetricSeries(metric_id="free_cash_flow", points=points, available=True)


def _margin_series(
    income_statement: list[dict],
    numerator_field: str,
    denominator_field: str,
    metric_id: str,
    source_limits: list[str],
) -> MetricSeries:
    points = []
    for row in reversed(income_statement):
        if row.get("fiscal_date") is None:
            continue
        num, den = row.get(numerator_field), row.get(denominator_field)
        if num is not None and den:
            points.append(Point(date=row["fiscal_date"], value=float(num) / float(den)))
    if not points:
        return _unavailable(metric_id, source_limits)
    return MetricSeries(metric_id=metric_id, points=points, available=True)
