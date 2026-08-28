import pytest

from financial_charts.charts.catalog import available_charts, get_chart


def test_available_charts_includes_all_builtins_and_fcf_margin():
    names = {chart.name for chart in available_charts()}
    assert names == {
        "price",
        "revenue",
        "net_income",
        "free_cash_flow",
        "eps",
        "margins",
        "fcf_margin",
        "ebitda",
        "expenses",
        "dividends",
        "shares_outstanding",
        "cash_and_debt",
        "assets_equity_liabilities",
        "debt_leverage",
        "ratios",
        "return_on_capital",
        "valuation",
        "market_cap",
        "pe_ratio",
        "dividend_yield",
        "return_on_equity",
    }


def test_get_chart_resolves_by_id():
    assert get_chart("price").name == "price"


def test_get_chart_unknown_id_raises_key_error():
    with pytest.raises(KeyError):
        get_chart("not-a-real-chart")
