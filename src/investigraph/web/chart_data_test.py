import json
from datetime import date, timedelta

from investigraph.charts.catalog import available_charts, get_chart
from investigraph.charts.registry import register_chart_set
from investigraph.template.models import (
    CompanyFundamentals,
    Currency,
    Market,
    MetricSeries,
    Money,
    Period,
    Point,
    Unit,
)
from investigraph.web.chart_data import ChartDataResponse, build_chart_specs

# Local, independent fixture helpers (not charts/builtins/_test_helpers.py, which
# is private to that package) — matches this module's own no-shared-internals design.


def _money_series(
    metric_id: str,
    points: list[tuple[date, float]],
    currency: Currency = Currency.USD,
    scale: Unit = Unit.ONES,
) -> MetricSeries:
    return MetricSeries(
        metric_id=metric_id,
        points=[
            Point(date=d, value=Money(value=v, currency=currency, scale=scale))
            for d, v in points
        ],
        available=True,
    )


def _float_series(metric_id: str, points: list[tuple[date, float]]) -> MetricSeries:
    return MetricSeries(
        metric_id=metric_id,
        points=[Point(date=d, value=v) for d, v in points],
        available=True,
    )


def _fundamentals_with(
    series: dict[str, MetricSeries], currency: Currency = Currency.USD
) -> CompanyFundamentals:
    return CompanyFundamentals(
        ticker="TEST",
        market=Market.US,
        currency=currency,
        period=Period.ANNUAL,
        range="5y",
        series=series,
    )


_D = date(2020, 1, 1)


def _full_fundamentals() -> CompanyFundamentals:
    """Every metric any catalog chart requires, all on one common date."""
    return _fundamentals_with(
        {
            "price": _money_series("price", [(_D, 100)]),
            "revenue": _money_series("revenue", [(_D, 500)], scale=Unit.MILLIONS),
            "net_income": _money_series("net_income", [(_D, 50)], scale=Unit.MILLIONS),
            "free_cash_flow": _money_series(
                "free_cash_flow", [(_D, 40)], scale=Unit.MILLIONS
            ),
            "eps": _money_series("eps", [(_D, 2)]),
            "gross_margin": _float_series("gross_margin", [(_D, 0.4)]),
            "net_margin": _float_series("net_margin", [(_D, 0.1)]),
            "ebitda": _money_series("ebitda", [(_D, 80)], scale=Unit.MILLIONS),
            "research_and_development": _money_series(
                "research_and_development", [(_D, 20)], scale=Unit.MILLIONS
            ),
            "selling_general_administrative": _money_series(
                "selling_general_administrative", [(_D, 15)], scale=Unit.MILLIONS
            ),
            "dividends_paid": _money_series(
                "dividends_paid", [(_D, 10)], scale=Unit.MILLIONS
            ),
            "shares_outstanding": _float_series(
                "shares_outstanding", [(_D, 25_000_000)]
            ),
            "cash_and_equivalents": _money_series(
                "cash_and_equivalents", [(_D, 30)], scale=Unit.MILLIONS
            ),
            "total_debt": _money_series("total_debt", [(_D, 60)], scale=Unit.MILLIONS),
            "total_assets": _money_series(
                "total_assets", [(_D, 300)], scale=Unit.MILLIONS
            ),
            "total_equity": _money_series(
                "total_equity", [(_D, 150)], scale=Unit.MILLIONS
            ),
            "total_liabilities": _money_series(
                "total_liabilities", [(_D, 150)], scale=Unit.MILLIONS
            ),
            "total_current_assets": _money_series(
                "total_current_assets", [(_D, 100)], scale=Unit.MILLIONS
            ),
            "total_current_liabilities": _money_series(
                "total_current_liabilities", [(_D, 50)], scale=Unit.MILLIONS
            ),
            "ebit": _money_series("ebit", [(_D, 70)], scale=Unit.MILLIONS),
        }
    )


def _specs_for(chart_names: list[str], fundamentals: CompanyFundamentals) -> list[dict]:
    set_name = "custom:chart_data_test:" + ",".join(chart_names)
    register_chart_set(set_name, [get_chart(name) for name in chart_names])
    return build_chart_specs(fundamentals, set_name)


def test_missing_required_metric_is_no_data():
    fundamentals = _fundamentals_with({})

    [spec] = _specs_for(["revenue"], fundamentals)

    assert spec == {"kind": "no_data", "name": "revenue", "title": "Revenue"}


def test_money_bar_uses_raw_scale_relative_value_not_base_units():
    fundamentals = _fundamentals_with(
        {"revenue": _money_series("revenue", [(_D, 12.3)], scale=Unit.MILLIONS)}
    )

    [spec] = _specs_for(["revenue"], fundamentals)

    assert spec["kind"] == "bar"
    assert spec["series"] == [{"label": "Revenue", "dates": [_D], "values": [12.3]}]


def test_money_line_uses_base_units_across_series():
    fundamentals = _fundamentals_with(
        {
            "cash_and_equivalents": _money_series(
                "cash_and_equivalents", [(_D, 30)], scale=Unit.MILLIONS
            ),
            "total_debt": _money_series("total_debt", [(_D, 5)], scale=Unit.MILLIONS),
        }
    )

    [spec] = _specs_for(["cash_and_debt"], fundamentals)

    assert spec["kind"] == "line"
    cash, debt = spec["series"]
    assert cash == {"label": "Cash", "dates": [_D], "values": [30_000_000.0]}
    assert debt == {"label": "Total Debt", "dates": [_D], "values": [5_000_000.0]}


def test_margins_scales_raw_ratio_to_percent():
    fundamentals = _fundamentals_with(
        {
            "gross_margin": _float_series("gross_margin", [(_D, 0.4)]),
            "net_margin": _float_series("net_margin", [(_D, 0.1)]),
        }
    )

    [spec] = _specs_for(["margins"], fundamentals)

    gross, net = spec["series"]
    assert gross["values"] == [40.0]
    assert net["values"] == [10.0]


def test_margins_includes_operating_margin_when_ebit_and_revenue_available():
    fundamentals = _fundamentals_with(
        {
            "gross_margin": _float_series("gross_margin", [(_D, 0.4)]),
            "net_margin": _float_series("net_margin", [(_D, 0.1)]),
            "ebit": _money_series("ebit", [(_D, 30)], scale=Unit.MILLIONS),
            "revenue": _money_series("revenue", [(_D, 200)], scale=Unit.MILLIONS),
        }
    )

    [spec] = _specs_for(["margins"], fundamentals)

    gross, net, operating = spec["series"]
    assert operating["label"] == "Operating Margin"
    assert operating["values"] == [15.0]


def test_margins_omits_operating_margin_when_ebit_unavailable():
    fundamentals = _fundamentals_with(
        {
            "gross_margin": _float_series("gross_margin", [(_D, 0.4)]),
            "net_margin": _float_series("net_margin", [(_D, 0.1)]),
        }
    )

    [spec] = _specs_for(["margins"], fundamentals)

    labels = [s["label"] for s in spec["series"]]
    assert "Operating Margin" not in labels


def test_derived_percentage_line_fcf_margin():
    fundamentals = _fundamentals_with(
        {
            "free_cash_flow": _money_series(
                "free_cash_flow", [(_D, 40)], scale=Unit.MILLIONS
            ),
            "revenue": _money_series("revenue", [(_D, 200)], scale=Unit.MILLIONS),
        }
    )

    [spec] = _specs_for(["fcf_margin"], fundamentals)

    assert spec["kind"] == "line"
    assert spec["series"][0]["values"] == [20.0]


def test_derived_ratio_line_falls_back_to_no_data_when_dates_do_not_overlap():
    fundamentals = _fundamentals_with(
        {
            "total_debt": _money_series("total_debt", [(_D, 50)]),
            "total_equity": _money_series("total_equity", [(date(2021, 1, 1), 100)]),
        }
    )

    [spec] = _specs_for(["debt_leverage"], fundamentals)

    assert spec == {
        "kind": "no_data",
        "name": "debt_leverage",
        "title": "Debt / Financial Leverage",
    }


def test_return_on_capital_computes_both_roce_and_roic():
    fundamentals = _fundamentals_with(
        {
            "ebit": _money_series("ebit", [(_D, 20)], scale=Unit.MILLIONS),
            "total_assets": _money_series(
                "total_assets", [(_D, 300)], scale=Unit.MILLIONS
            ),
            "total_current_liabilities": _money_series(
                "total_current_liabilities", [(_D, 100)], scale=Unit.MILLIONS
            ),
            "net_income": _money_series("net_income", [(_D, 15)], scale=Unit.MILLIONS),
            "total_debt": _money_series("total_debt", [(_D, 50)], scale=Unit.MILLIONS),
            "total_equity": _money_series(
                "total_equity", [(_D, 200)], scale=Unit.MILLIONS
            ),
            "cash_and_equivalents": _money_series(
                "cash_and_equivalents", [(_D, 50)], scale=Unit.MILLIONS
            ),
        }
    )

    [spec] = _specs_for(["return_on_capital"], fundamentals)

    roce, roic = spec["series"]
    assert roce["label"] == "ROCE"
    assert roce["values"] == [10.0]
    assert roic["label"] == "ROIC"
    assert roic["values"] == [7.5]


def test_valuation_pairs_book_value_with_nearest_price_not_exact_date():
    fundamentals = _fundamentals_with(
        {
            "total_equity": _money_series(
                "total_equity", [(_D, 200)], scale=Unit.MILLIONS
            ),
            "shares_outstanding": _float_series(
                "shares_outstanding", [(_D, 10_000_000)]
            ),
            "price": _money_series(
                "price",
                [(date(2019, 12, 20), 25), (date(2020, 1, 10), 30)],
            ),
        }
    )

    [spec] = _specs_for(["valuation"], fundamentals)

    # book value/share = 200_000_000 / 10_000_000 = 20; nearest price to 2020-01-01
    # is 2020-01-10's 30 (9 days away) over 2019-12-20's 25 (12 days away).
    assert spec["series"][0]["values"] == [1.5]


def test_price_sma_only_emitted_once_enough_points_exist():
    fundamentals = _fundamentals_with(
        {
            "price": _money_series(
                "price", [(date(2020, 1, i + 1), 100) for i in range(10)]
            )
        }
    )

    [spec] = _specs_for(["price"], fundamentals)

    assert [s["label"] for s in spec["series"]] == ["Close"]


def test_price_sma_drawn_thin_and_markerless_close_left_alone():
    points = [(_D + timedelta(days=i), 100 + i) for i in range(55)]
    fundamentals = _fundamentals_with({"price": _money_series("price", points)})

    specs = _specs_for(["price"], fundamentals)
    response = ChartDataResponse(
        ticker="TEST", market="US", currency="USD", charts=specs
    )
    close, sma_50 = json.loads(response.model_dump_json())["charts"][0]["series"]

    assert (close["label"], close["width"], close["markers"]) == ("Close", None, True)
    assert (sma_50["label"], sma_50["width"], sma_50["markers"]) == ("SMA 50", 1, False)


def test_price_sma_warmup_nan_launders_to_json_null():
    points = [(_D + timedelta(days=i), 100 + i) for i in range(55)]
    fundamentals = _fundamentals_with({"price": _money_series("price", points)})

    specs = _specs_for(["price"], fundamentals)
    response = ChartDataResponse(
        ticker="TEST", market="US", currency="USD", charts=specs
    )
    raw = response.model_dump_json()

    assert "NaN" not in raw
    parsed = json.loads(raw)
    sma_50 = next(s for s in parsed["charts"][0]["series"] if s["label"] == "SMA 50")
    assert sma_50["values"][0] is None


def test_market_cap_is_a_daily_line_of_price_times_as_of_shares():
    fundamentals = _fundamentals_with(
        {
            "price": _money_series("price", [(_D, 50), (date(2020, 1, 2), 60)]),
            "shares_outstanding": _float_series(
                "shares_outstanding", [(_D, 1_000_000)]
            ),
        }
    )

    [spec] = _specs_for(["market_cap"], fundamentals)

    assert spec["kind"] == "line"
    assert spec["series"] == [
        {
            "label": "Market Cap",
            "dates": [_D, date(2020, 1, 2)],
            "values": [50_000_000.0, 60_000_000.0],
            "markers": False,
        }
    ]


def test_pe_ratio_line():
    fundamentals = _fundamentals_with(
        {
            "price": _money_series("price", [(_D, 20)]),
            "eps": _money_series("eps", [(_D, 2)]),
        }
    )

    [spec] = _specs_for(["pe_ratio"], fundamentals)

    assert spec["kind"] == "line"
    assert spec["series"][0]["values"] == [10.0]
    assert spec["series"][0]["markers"] is False


def test_pe_ratio_zero_eps_is_no_data():
    fundamentals = _fundamentals_with(
        {
            "price": _money_series("price", [(_D, 20)]),
            "eps": _money_series("eps", [(_D, 0)]),
        }
    )

    [spec] = _specs_for(["pe_ratio"], fundamentals)

    assert spec["kind"] == "no_data"


def test_dividend_yield_line():
    fundamentals = _fundamentals_with(
        {
            "price": _money_series("price", [(_D, 100)]),
            "dividends_paid": _money_series("dividends_paid", [(_D, 2)]),
            "shares_outstanding": _float_series("shares_outstanding", [(_D, 1)]),
        }
    )

    [spec] = _specs_for(["dividend_yield"], fundamentals)

    assert spec["kind"] == "line"
    assert spec["series"][0]["values"] == [2.0]


def test_return_on_equity_line():
    fundamentals = _fundamentals_with(
        {
            "net_income": _money_series("net_income", [(_D, 15)], scale=Unit.MILLIONS),
            "total_equity": _money_series(
                "total_equity", [(_D, 200)], scale=Unit.MILLIONS
            ),
        }
    )

    [spec] = _specs_for(["return_on_equity"], fundamentals)

    assert spec["kind"] == "line"
    assert spec["series"][0]["values"] == [7.5]


def test_every_catalog_chart_has_a_shaper_and_does_not_crash():
    fundamentals = _full_fundamentals()
    set_name = "custom:chart_data_test:everything"
    register_chart_set(set_name, available_charts())

    specs = build_chart_specs(fundamentals, set_name)

    assert len(specs) == len(available_charts())
    for spec in specs:
        assert spec["kind"] in {"bar", "line", "no_data"}


def test_chart_data_response_round_trips_every_kind():
    fundamentals = _full_fundamentals()
    set_name = "custom:chart_data_test:round_trip"
    register_chart_set(set_name, available_charts())

    specs = build_chart_specs(fundamentals, set_name)
    response = ChartDataResponse(
        ticker=fundamentals.ticker,
        market=fundamentals.market.value,
        currency=fundamentals.currency.value,
        source_limits=fundamentals.source_limits,
        charts=specs,
    )

    parsed = json.loads(response.model_dump_json())
    assert parsed["ticker"] == "TEST"
    assert len(parsed["charts"]) == len(available_charts())
