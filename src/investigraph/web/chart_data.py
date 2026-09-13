"""Shape a `CompanyFundamentals` chart set into JSON for the interactive web dashboard.

Independent of matplotlib and of every `charts/builtins/*.py` file: each chart's
*data prep* (as opposed to its matplotlib drawing) is re-derived here from the
template, reusing only published functions (`charts.base.currency_symbol`,
`template.derived.resolve`/the `DerivedMetric` constants,
`template.trailing.resolve_trailing`/the `TrailingMetric` constants). Two charts
(the valuation nearest-price join, price's SMA overlay) have their small inline
math re-implemented here rather than imported, since it isn't externalized from
its chart file today — see PROGRESS.md for the accepted duplication/drift
trade-off.

Values are laundered through Pydantic (`ChartDataResponse.model_dump_json()`),
never `flask.jsonify()`: `jsonify` reproduces raw `NaN` tokens (invalid JSON),
which pandas SMA warm-up periods and other computed ratios can produce.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Annotated, Callable, Literal

import pandas as pd
from pydantic import BaseModel, Field

from investigraph.charts.base import currency_symbol
from investigraph.charts.registry import get_chart_set
from investigraph.template.derived import (
    BOOK_VALUE_PER_SHARE,
    CURRENT_RATIO,
    DEBT_TO_EQUITY,
    FCF_MARGIN,
    OPERATING_MARGIN,
    ROCE,
    ROIC,
    DerivedMetric,
    resolve,
)
from investigraph.template.models import CompanyFundamentals, Point
from investigraph.template.trailing import (
    DIVIDEND_YIELD_TTM,
    MARKET_CAP,
    PE_RATIO_TTM,
    ROE_TTM,
    TrailingMetric,
    resolve_trailing,
)


class SeriesSpec(BaseModel):
    label: str
    dates: list[date]
    values: list[float]
    # Optional drawing hints for the browser: overlay lines (price's SMAs, the
    # P/E average line) are drawn thin and without per-point markers so the
    # primary series stands out; `dash` further distinguishes a reference line
    # (e.g. the P/E average) from actual data.
    width: float | None = None
    markers: bool = True
    dash: str | None = None


class _ChartSpecBase(BaseModel):
    name: str
    title: str


class BarChartSpec(_ChartSpecBase):
    kind: Literal["bar"] = "bar"
    y_label: str
    series: list[SeriesSpec]


class LineChartSpec(_ChartSpecBase):
    kind: Literal["line"] = "line"
    y_label: str
    series: list[SeriesSpec]


class NoDataChartSpec(_ChartSpecBase):
    kind: Literal["no_data"] = "no_data"


ChartSpec = Annotated[
    BarChartSpec | LineChartSpec | NoDataChartSpec,
    Field(discriminator="kind"),
]


class ChartDataResponse(BaseModel):
    ticker: str
    market: str
    currency: str
    source_limits: list[str] = []
    charts: list[ChartSpec]


def build_chart_specs(
    fundamentals: CompanyFundamentals, chart_set_name: str
) -> list[dict]:
    """One JSON-serializable chart spec dict per chart in `chart_set_name`, in order.

    Mirrors `charts.base.render_or_no_data`'s required-metrics gate; a chart
    whose gate passes can still shape to `None` (e.g. a derived value with no
    overlapping dates across otherwise-available inputs), which also degrades
    to a `no_data` spec, same as the matplotlib path.
    """
    specs: list[dict] = []
    for chart in get_chart_set(chart_set_name):
        missing = [
            metric_id
            for metric_id in chart.required_metrics
            if (series := fundamentals.series.get(metric_id)) is None
            or not series.available
        ]
        body = None if missing else _SHAPERS[chart.name](fundamentals)
        if body is None:
            specs.append({"kind": "no_data", "name": chart.name, "title": chart.title})
        else:
            specs.append({"name": chart.name, "title": chart.title, **body})
    return specs


def _money_bar(metric_id: str) -> Callable[[CompanyFundamentals], dict]:
    """Single-series bar of a raw `Money.value` (not base units) — matches
    `render_money_bar`'s scale-relative plotting exactly."""

    def shaper(fundamentals: CompanyFundamentals) -> dict:
        points = fundamentals.series[metric_id].points
        label = metric_id.replace("_", " ").title()
        return {
            "kind": "bar",
            "y_label": f"{label} ({currency_symbol(fundamentals)})",
            "series": [
                {
                    "label": label,
                    "dates": [p.date for p in points],
                    "values": [p.value.value for p in points],
                }
            ],
        }

    return shaper


def _shares_outstanding(fundamentals: CompanyFundamentals) -> dict:
    points = fundamentals.series["shares_outstanding"].points
    return {
        "kind": "bar",
        "y_label": "Shares",
        "series": [
            {
                "label": "Shares",
                "dates": [p.date for p in points],
                "values": [p.value for p in points],
            }
        ],
    }


def _money_line(
    pairs: list[tuple[str, str]],
) -> Callable[[CompanyFundamentals], dict]:
    """Multi-series line of `Money.as_base_units()` — matches `render_money_line`."""

    def shaper(fundamentals: CompanyFundamentals) -> dict:
        series = []
        for metric_id, label in pairs:
            points = fundamentals.series[metric_id].points
            series.append(
                {
                    "label": label,
                    "dates": [p.date for p in points],
                    "values": [p.value.as_base_units() for p in points],
                }
            )
        return {
            "kind": "line",
            "y_label": f"({currency_symbol(fundamentals)})",
            "series": series,
        }

    return shaper


def _margins(fundamentals: CompanyFundamentals) -> dict:
    series = []
    for metric_id, label in [
        ("gross_margin", "Gross Margin"),
        ("net_margin", "Net Margin"),
    ]:
        points = fundamentals.series[metric_id].points
        series.append(
            {
                "label": label,
                "dates": [p.date for p in points],
                "values": [p.value * 100 for p in points],
            }
        )

    # Operating margin is derived (ebit / revenue) rather than a source-supplied
    # series like gross/net margin above, so it isn't in `required_metrics` — it
    # degrades to simply omitting its line instead of blanking the whole chart
    # when `ebit` or `revenue` is unavailable for this ticker/source.
    operating_margin = resolve(fundamentals, OPERATING_MARGIN)
    if operating_margin.available:
        series.append(
            {
                "label": "Operating Margin",
                "dates": [p.date for p in operating_margin.points],
                "values": [p.value * 100 for p in operating_margin.points],
            }
        )

    return {"kind": "line", "y_label": "Margin (%)", "series": series}


def _percentage_line_derived(
    derived: DerivedMetric, label: str, y_label: str
) -> Callable[[CompanyFundamentals], dict | None]:
    def shaper(fundamentals: CompanyFundamentals) -> dict | None:
        series = resolve(fundamentals, derived)
        if not series.available:
            return None
        return {
            "kind": "line",
            "y_label": y_label,
            "series": [
                {
                    "label": label,
                    "dates": [p.date for p in series.points],
                    "values": [p.value * 100 for p in series.points],
                }
            ],
        }

    return shaper


def _ratio_line_derived(
    derived: DerivedMetric, label: str, y_label: str
) -> Callable[[CompanyFundamentals], dict | None]:
    def shaper(fundamentals: CompanyFundamentals) -> dict | None:
        series = resolve(fundamentals, derived)
        if not series.available:
            return None
        return {
            "kind": "line",
            "y_label": y_label,
            "series": [
                {
                    "label": label,
                    "dates": [p.date for p in series.points],
                    "values": [p.value for p in series.points],
                }
            ],
        }

    return shaper


def _return_on_capital(fundamentals: CompanyFundamentals) -> dict | None:
    roce = resolve(fundamentals, ROCE)
    roic = resolve(fundamentals, ROIC)
    if not roce.available or not roic.available:
        return None
    return {
        "kind": "line",
        "y_label": "Return (%)",
        "series": [
            {
                "label": "ROCE",
                "dates": [p.date for p in roce.points],
                "values": [p.value * 100 for p in roce.points],
            },
            {
                "label": "ROIC",
                "dates": [p.date for p in roic.points],
                "values": [p.value * 100 for p in roic.points],
            },
        ],
    }


def _nearest_price(price_points: list[Point], target: date) -> float:
    closest = min(price_points, key=lambda p: abs((p.date - target).days))
    return closest.value.value


def _valuation(fundamentals: CompanyFundamentals) -> dict | None:
    book_value = resolve(fundamentals, BOOK_VALUE_PER_SHARE)
    price_points = fundamentals.series["price"].points
    equity_points = fundamentals.series["total_equity"].points
    if not book_value.available or not price_points or not equity_points:
        return None
    if price_points[0].value.currency != equity_points[0].value.currency:
        return None

    dates = []
    values = []
    for point in book_value.points:
        if point.value == 0:
            continue
        dates.append(point.date)
        values.append(_nearest_price(price_points, point.date) / point.value)

    if not values:
        return None
    return {
        "kind": "line",
        "y_label": "Price / Book (x)",
        "series": [{"label": "P/B", "dates": dates, "values": values}],
    }


def _price(fundamentals: CompanyFundamentals) -> dict:
    points = fundamentals.series["price"].points
    dates = [p.date for p in points]
    closes = pd.Series([p.value.value for p in points], index=dates)

    series = [{"label": "Close", "dates": dates, "values": closes.tolist()}]
    for window in (50, 150, 200):
        if len(closes) >= window:
            sma = closes.rolling(window=window).mean()
            series.append(
                {
                    "label": f"SMA {window}",
                    "dates": dates,
                    "values": sma.tolist(),
                    "width": 1,
                    "markers": False,
                }
            )

    return {
        "kind": "line",
        "y_label": f"Price ({currency_symbol(fundamentals)})",
        "series": series,
    }


def _trailing_ratio_line(
    metric: TrailingMetric, label: str, y_label: str, markers: bool = True
) -> Callable[[CompanyFundamentals], dict | None]:
    def shaper(fundamentals: CompanyFundamentals) -> dict | None:
        series = resolve_trailing(fundamentals, metric)
        if not series.available:
            return None
        return {
            "kind": "line",
            "y_label": y_label,
            "series": [
                {
                    "label": label,
                    "dates": [p.date for p in series.points],
                    "values": [p.value for p in series.points],
                    "markers": markers,
                }
            ],
        }

    return shaper


def _trailing_percentage_line(
    metric: TrailingMetric, label: str, y_label: str, markers: bool = True
) -> Callable[[CompanyFundamentals], dict | None]:
    def shaper(fundamentals: CompanyFundamentals) -> dict | None:
        series = resolve_trailing(fundamentals, metric)
        if not series.available:
            return None
        return {
            "kind": "line",
            "y_label": y_label,
            "series": [
                {
                    "label": label,
                    "dates": [p.date for p in series.points],
                    "values": [p.value * 100 for p in series.points],
                    "markers": markers,
                }
            ],
        }

    return shaper


def _pe_ratio(fundamentals: CompanyFundamentals) -> dict | None:
    series = resolve_trailing(fundamentals, PE_RATIO_TTM)
    if not series.available:
        return None
    dates = [p.date for p in series.points]
    values = [p.value for p in series.points]

    valid = [v for v in values if not math.isnan(v)]
    lines = [{"label": "P/E", "dates": dates, "values": values, "markers": False}]
    if valid:
        average = sum(valid) / len(valid)
        lines.append(
            {
                "label": f"Avg {average:.1f}x",
                "dates": dates,
                "values": [average] * len(dates),
                "markers": False,
                "width": 1,
                "dash": "dash",
            }
        )

    return {"kind": "line", "y_label": "P/E (x)", "series": lines}


def _market_cap(fundamentals: CompanyFundamentals) -> dict | None:
    series = resolve_trailing(fundamentals, MARKET_CAP)
    if not series.available:
        return None
    return {
        "kind": "line",
        "y_label": f"Market Cap ({currency_symbol(fundamentals)})",
        "series": [
            {
                "label": "Market Cap",
                "dates": [p.date for p in series.points],
                "values": [p.value.as_base_units() for p in series.points],
                "markers": False,
            }
        ],
    }


_SHAPERS: dict[str, Callable[[CompanyFundamentals], dict | None]] = {
    "price": _price,
    "revenue": _money_bar("revenue"),
    "net_income": _money_bar("net_income"),
    "free_cash_flow": _money_bar("free_cash_flow"),
    "eps": _money_bar("eps"),
    "margins": _margins,
    "fcf_margin": _percentage_line_derived(FCF_MARGIN, "FCF Margin", "FCF Margin (%)"),
    "ebitda": _money_bar("ebitda"),
    "expenses": _money_line(
        [
            ("research_and_development", "R&D"),
            ("selling_general_administrative", "SG&A"),
        ]
    ),
    "dividends": _money_bar("dividends_paid"),
    "shares_outstanding": _shares_outstanding,
    "cash_and_debt": _money_line(
        [("cash_and_equivalents", "Cash"), ("total_debt", "Total Debt")]
    ),
    "assets_equity_liabilities": _money_line(
        [
            ("total_assets", "Assets"),
            ("total_equity", "Equity"),
            ("total_liabilities", "Liabilities"),
        ]
    ),
    "debt_leverage": _ratio_line_derived(
        DEBT_TO_EQUITY, "Debt / Equity", "Debt / Equity (x)"
    ),
    "ratios": _ratio_line_derived(CURRENT_RATIO, "Current Ratio", "Current Ratio (x)"),
    "return_on_capital": _return_on_capital,
    "valuation": _valuation,
    "market_cap": _market_cap,
    "pe_ratio": _pe_ratio,
    "dividend_yield": _trailing_percentage_line(
        DIVIDEND_YIELD_TTM, "Dividend Yield", "Dividend Yield (%)", markers=False
    ),
    "return_on_equity": _trailing_percentage_line(ROE_TTM, "ROE", "ROE (%)"),
}
