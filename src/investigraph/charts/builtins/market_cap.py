from matplotlib.axes import Axes

from financial_charts.charts.base import currency_symbol, draw_no_data
from financial_charts.template.models import CompanyFundamentals
from financial_charts.template.trailing import MARKET_CAP, resolve_trailing


class MarketCapChart:
    name = "market_cap"
    title = "Market Cap"
    required_metrics = ["price", "shares_outstanding"]

    def render(self, ax: Axes, fundamentals: CompanyFundamentals) -> None:
        series = resolve_trailing(fundamentals, MARKET_CAP)
        if not series.available:
            draw_no_data(ax)
            return
        dates = [p.date for p in series.points]
        values = [p.value.as_base_units() for p in series.points]
        ax.plot(dates, values, label="Market Cap", linewidth=1)
        ax.set_ylabel(f"Market Cap ({currency_symbol(fundamentals)})")
        ax.legend(fontsize=7, loc="upper left")
