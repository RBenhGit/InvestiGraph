from financial_charts.charts.base import Chart
from financial_charts.charts.builtins.assets_equity_liabilities import (
    AssetsEquityLiabilitiesChart,
)
from financial_charts.charts.builtins.cash_and_debt import CashAndDebtChart
from financial_charts.charts.builtins.debt_leverage import DebtLeverageChart
from financial_charts.charts.builtins.dividend_yield import DividendYieldChart
from financial_charts.charts.builtins.dividends import DividendsChart
from financial_charts.charts.builtins.ebitda import EBITDAChart
from financial_charts.charts.builtins.eps import EPSChart
from financial_charts.charts.builtins.expenses import ExpensesChart
from financial_charts.charts.builtins.fcf_margin import FCFMarginChart
from financial_charts.charts.builtins.free_cash_flow import FreeCashFlowChart
from financial_charts.charts.builtins.margins import MarginsChart
from financial_charts.charts.builtins.market_cap import MarketCapChart
from financial_charts.charts.builtins.net_income import NetIncomeChart
from financial_charts.charts.builtins.pe_ratio import PERatioChart
from financial_charts.charts.builtins.price import PriceChart
from financial_charts.charts.builtins.ratios import RatiosChart
from financial_charts.charts.builtins.return_on_capital import ReturnOnCapitalChart
from financial_charts.charts.builtins.return_on_equity import ReturnOnEquityChart
from financial_charts.charts.builtins.revenue import RevenueChart
from financial_charts.charts.builtins.shares_outstanding import (
    SharesOutstandingChart,
)
from financial_charts.charts.builtins.valuation import ValuationChart

_CHARTS: list[Chart] = [
    PriceChart(),
    RevenueChart(),
    NetIncomeChart(),
    FreeCashFlowChart(),
    EPSChart(),
    MarginsChart(),
    FCFMarginChart(),
    EBITDAChart(),
    ExpensesChart(),
    DividendsChart(),
    SharesOutstandingChart(),
    CashAndDebtChart(),
    AssetsEquityLiabilitiesChart(),
    DebtLeverageChart(),
    RatiosChart(),
    ReturnOnCapitalChart(),
    ValuationChart(),
    MarketCapChart(),
    PERatioChart(),
    DividendYieldChart(),
    ReturnOnEquityChart(),
]


def available_charts() -> list[Chart]:
    """Every chart registered in the catalog — what a user's picker chooses from."""
    return list(_CHARTS)


def get_chart(chart_id: str) -> Chart:
    for chart in _CHARTS:
        if chart.name == chart_id:
            return chart
    raise KeyError(
        f"unknown chart {chart_id!r}; available charts: "
        f"{sorted(c.name for c in _CHARTS)}"
    )
