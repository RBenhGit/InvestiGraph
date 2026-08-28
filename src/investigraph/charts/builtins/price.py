import pandas as pd
from matplotlib.axes import Axes

from financial_charts.charts.base import currency_symbol
from financial_charts.template.models import CompanyFundamentals

_SMA_WINDOWS = (50, 150, 200)


class PriceChart:
    name = "price"
    title = "Price"
    required_metrics = ["price"]

    def render(self, ax: Axes, fundamentals: CompanyFundamentals) -> None:
        points = fundamentals.series["price"].points
        dates = [p.date for p in points]
        closes = pd.Series([p.value.value for p in points], index=dates)

        ax.plot(dates, closes.to_numpy(), label="Close", color="black", linewidth=1)
        for window in _SMA_WINDOWS:
            if len(closes) >= window:
                sma = closes.rolling(window=window).mean()
                ax.plot(dates, sma.to_numpy(), label=f"SMA {window}", linewidth=0.8)

        ax.set_ylabel(f"Price ({currency_symbol(fundamentals)})")
        ax.legend(fontsize=7, loc="upper left")
