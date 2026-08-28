import pandas as pd
import yfinance as yf

from financial_charts.sources.base import Capability, SourceUnavailable, TickerNotFound
from financial_charts.sources.currency import AGOROT_CODE, map_currency
from financial_charts.sources.yfinance.capability import CAPABILITY
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

# yfinance `history(period=...)` accepts each of these directly.
_YFINANCE_PERIODS = {
    "6m": "6mo",
    "1y": "1y",
    "3y": "3y",
    "5y": "5y",
    "10y": "10y",
    "max": "max",
}


class YFinanceAdapter:
    def capability(self) -> Capability:
        return CAPABILITY

    def fetch(
        self, ticker: str, market: Market, period: Period, range: str
    ) -> CompanyFundamentals:
        """Fetch and translate any yfinance/network failure to `SourceUnavailable`.

        `TickerNotFound` is raised by `_fetch` itself and passes through
        unchanged so callers can tell "no such ticker" from "source is down"
        (only the latter triggers the stale-cache fallback).
        """
        try:
            return self._fetch(ticker, market, period, range)
        except TickerNotFound:
            raise
        except Exception as exc:
            raise SourceUnavailable(str(exc)) from exc

    def _fetch(
        self, ticker: str, market: Market, period: Period, range: str
    ) -> CompanyFundamentals:
        yf_ticker = yf.Ticker(ticker)
        info = yf_ticker.info
        history = yf_ticker.history(period=_range_to_yfinance_period(range))
        if history.empty and len(info) <= 1:
            raise TickerNotFound(ticker)

        price_currency = map_currency(info.get("currency"))
        financial_currency = map_currency(info.get("financialCurrency"))
        display_currency = Currency.ILS if market == Market.TASE else Currency.USD

        series: dict[str, MetricSeries] = {}
        source_limits: list[str] = []

        series["price"] = _price_series(
            history, info.get("currency"), price_currency, source_limits
        )

        # `range` only bounds this price fetch (via `history(period=...)`);
        # yfinance's `financials`/`cashflow`/`balance_sheet` properties return
        # whatever depth the API gives regardless of the requested range.
        statements = (
            (yf_ticker.financials, yf_ticker.cashflow, yf_ticker.balance_sheet)
            if period == Period.ANNUAL
            else (
                yf_ticker.quarterly_financials,
                yf_ticker.quarterly_cashflow,
                yf_ticker.quarterly_balance_sheet,
            )
        )
        financials, cashflow, balance_sheet = statements

        series["revenue"] = _statement_series(
            financials,
            "Total Revenue",
            financial_currency,
            Unit.ONES,
            "revenue",
            source_limits,
        )
        series["net_income"] = _statement_series(
            financials,
            "Net Income",
            financial_currency,
            Unit.ONES,
            "net_income",
            source_limits,
        )
        series["eps"] = _statement_series(
            financials,
            "Diluted EPS",
            financial_currency,
            Unit.ONES,
            "eps",
            source_limits,
        )
        series["free_cash_flow"] = _statement_series(
            cashflow,
            "Free Cash Flow",
            financial_currency,
            Unit.ONES,
            "free_cash_flow",
            source_limits,
        )
        series["gross_margin"] = _margin_series(
            financials, "Gross Profit", "Total Revenue", "gross_margin", source_limits
        )
        series["net_margin"] = _margin_series(
            financials, "Net Income", "Total Revenue", "net_margin", source_limits
        )
        series["ebitda"] = _statement_series(
            financials, "EBITDA", financial_currency, Unit.ONES, "ebitda", source_limits
        )
        series["research_and_development"] = _statement_series(
            financials,
            "Research And Development",
            financial_currency,
            Unit.ONES,
            "research_and_development",
            source_limits,
        )
        series["selling_general_administrative"] = _statement_series(
            financials,
            "Selling General And Administration",
            financial_currency,
            Unit.ONES,
            "selling_general_administrative",
            source_limits,
        )
        series["dividends_paid"] = _statement_series(
            cashflow,
            "Cash Dividends Paid",
            financial_currency,
            Unit.ONES,
            "dividends_paid",
            source_limits,
            absolute=True,
        )
        series["shares_outstanding"] = _statement_float_series(
            financials,
            "Diluted Average Shares",
            "shares_outstanding",
            source_limits,
        )
        series["ebit"] = _statement_series(
            financials, "EBIT", financial_currency, Unit.ONES, "ebit", source_limits
        )
        series["total_assets"] = _statement_series(
            balance_sheet,
            "Total Assets",
            financial_currency,
            Unit.ONES,
            "total_assets",
            source_limits,
        )
        series["total_liabilities"] = _statement_series(
            balance_sheet,
            "Total Liabilities Net Minority Interest",
            financial_currency,
            Unit.ONES,
            "total_liabilities",
            source_limits,
        )
        series["total_equity"] = _statement_series(
            balance_sheet,
            "Stockholders Equity",
            financial_currency,
            Unit.ONES,
            "total_equity",
            source_limits,
        )
        series["cash_and_equivalents"] = _statement_series(
            balance_sheet,
            "Cash And Cash Equivalents",
            financial_currency,
            Unit.ONES,
            "cash_and_equivalents",
            source_limits,
        )
        series["total_debt"] = _statement_series(
            balance_sheet,
            "Total Debt",
            financial_currency,
            Unit.ONES,
            "total_debt",
            source_limits,
        )
        series["total_current_assets"] = _statement_series(
            balance_sheet,
            "Current Assets",
            financial_currency,
            Unit.ONES,
            "total_current_assets",
            source_limits,
        )
        series["total_current_liabilities"] = _statement_series(
            balance_sheet,
            "Current Liabilities",
            financial_currency,
            Unit.ONES,
            "total_current_liabilities",
            source_limits,
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


def _range_to_yfinance_period(range: str) -> str:
    return _YFINANCE_PERIODS.get(range.lower(), "max")


def _unavailable(metric_id: str, source_limits: list[str]) -> MetricSeries:
    """A metric with no usable data for this ticker: note why, and mark it unavailable."""
    source_limits.append(f"{metric_id}: no data available for this ticker")
    return MetricSeries(metric_id=metric_id, points=[], available=False)


def _price_series(
    history: pd.DataFrame,
    raw_currency_code: str | None,
    currency: Currency | None,
    source_limits: list[str],
) -> MetricSeries:
    if history.empty or currency is None:
        return _unavailable("price", source_limits)

    is_agorot = raw_currency_code == AGOROT_CODE
    points = [
        Point(
            date=idx.date(),
            value=Money(
                value=(row["Close"] / 100 if is_agorot else row["Close"]),
                currency=currency,
                scale=Unit.ONES,
            ),
        )
        for idx, row in history.iterrows()
        # yfinance reports a NaN close for the current, still-open trading
        # day — must never surface as a real (or "latest") price point.
        if pd.notna(row["Close"])
    ]
    if not points:
        return _unavailable("price", source_limits)
    return MetricSeries(metric_id="price", points=points, available=True)


def _statement_series(
    statement: pd.DataFrame,
    row_name: str,
    currency: Currency | None,
    scale: Unit,
    metric_id: str,
    source_limits: list[str],
    absolute: bool = False,
) -> MetricSeries:
    if statement.empty or row_name not in statement.index or currency is None:
        return _unavailable(metric_id, source_limits)

    row = statement.loc[row_name]
    points = [
        Point(
            date=col.date(),
            value=Money(
                value=abs(float(val)) if absolute else float(val),
                currency=currency,
                scale=scale,
            ),
        )
        for col, val in row.items()
        if pd.notna(val)
    ]
    # yfinance's statement columns come back newest-first; sort ascending to
    # match price and Twelve Data so every series in one CompanyFundamentals
    # runs the same chronological direction.
    points.sort(key=lambda p: p.date)
    if not points:
        return _unavailable(metric_id, source_limits)
    return MetricSeries(metric_id=metric_id, points=points, available=True)


def _statement_float_series(
    statement: pd.DataFrame,
    row_name: str,
    metric_id: str,
    source_limits: list[str],
) -> MetricSeries:
    """Like `_statement_series` but for a plain (non-Money) numeric row, e.g. a share count."""
    if statement.empty or row_name not in statement.index:
        return _unavailable(metric_id, source_limits)

    row = statement.loc[row_name]
    points = [
        Point(date=col.date(), value=float(val))
        for col, val in row.items()
        if pd.notna(val)
    ]
    points.sort(key=lambda p: p.date)
    if not points:
        return _unavailable(metric_id, source_limits)
    return MetricSeries(metric_id=metric_id, points=points, available=True)


def _margin_series(
    financials: pd.DataFrame,
    numerator_row: str,
    denominator_row: str,
    metric_id: str,
    source_limits: list[str],
) -> MetricSeries:
    if (
        financials.empty
        or numerator_row not in financials.index
        or denominator_row not in financials.index
    ):
        return _unavailable(metric_id, source_limits)

    numerator = financials.loc[numerator_row]
    denominator = financials.loc[denominator_row]
    points = []
    for col in financials.columns:
        num, den = numerator.get(col), denominator.get(col)
        if pd.notna(num) and pd.notna(den) and den != 0:
            points.append(Point(date=col.date(), value=float(num) / float(den)))
    points.sort(key=lambda p: p.date)
    if not points:
        return _unavailable(metric_id, source_limits)
    return MetricSeries(metric_id=metric_id, points=points, available=True)
