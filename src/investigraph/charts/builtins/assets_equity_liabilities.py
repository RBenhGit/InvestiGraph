from matplotlib.axes import Axes

from financial_charts.charts.base import render_money_line
from financial_charts.template.models import CompanyFundamentals


class AssetsEquityLiabilitiesChart:
    name = "assets_equity_liabilities"
    title = "Assets / Equity / Liabilities"
    required_metrics = ["total_assets", "total_equity", "total_liabilities"]

    def render(self, ax: Axes, fundamentals: CompanyFundamentals) -> None:
        render_money_line(
            ax,
            fundamentals,
            [
                ("total_assets", "Assets"),
                ("total_equity", "Equity"),
                ("total_liabilities", "Liabilities"),
            ],
        )
