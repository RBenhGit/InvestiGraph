from investigraph.charts.base import Chart
from investigraph.charts.builtins.assets_equity_liabilities import (
    AssetsEquityLiabilitiesChart,
)
from investigraph.charts.builtins.cash_and_debt import CashAndDebtChart
from investigraph.charts.builtins.debt_leverage import DebtLeverageChart
from investigraph.charts.builtins.dividend_yield import DividendYieldChart
from investigraph.charts.builtins.dividends import DividendsChart
from investigraph.charts.builtins.ebitda import EBITDAChart
from investigraph.charts.builtins.eps import EPSChart
from investigraph.charts.builtins.expenses import ExpensesChart
from investigraph.charts.builtins.fcf_margin import FCFMarginChart
from investigraph.charts.builtins.free_cash_flow import FreeCashFlowChart
from investigraph.charts.builtins.margins import MarginsChart
from investigraph.charts.builtins.market_cap import MarketCapChart
from investigraph.charts.builtins.net_income import NetIncomeChart
from investigraph.charts.builtins.pe_ratio import PERatioChart
from investigraph.charts.builtins.price import PriceChart
from investigraph.charts.builtins.ratios import RatiosChart
from investigraph.charts.builtins.return_on_capital import ReturnOnCapitalChart
from investigraph.charts.builtins.return_on_equity import ReturnOnEquityChart
from investigraph.charts.builtins.revenue import RevenueChart
from investigraph.charts.builtins.shares_outstanding import (
    SharesOutstandingChart,
)
from investigraph.charts.builtins.valuation import ValuationChart

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
