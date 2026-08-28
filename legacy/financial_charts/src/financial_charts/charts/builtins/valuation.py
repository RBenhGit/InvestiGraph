from datetime import date

from matplotlib.axes import Axes

from financial_charts.charts.base import draw_no_data, render_ratio_line
from financial_charts.template.derived import BOOK_VALUE_PER_SHARE, resolve
from financial_charts.template.models import CompanyFundamentals, Point


class ValuationChart:
    name = "valuation"
    title = "Valuation (P/B)"
    required_metrics = ["price", "total_equity", "shares_outstanding"]

    def render(self, ax: Axes, fundamentals: CompanyFundamentals) -> None:
        book_value = resolve(fundamentals, BOOK_VALUE_PER_SHARE)
        price_points = fundamentals.series["price"].points
        equity_points = fundamentals.series["total_equity"].points
        if not book_value.available or not price_points or not equity_points:
            draw_no_data(ax)
            return
        if price_points[0].value.currency != equity_points[0].value.currency:
            # BOOK_VALUE_PER_SHARE's compute discards its Money currency tag
            # (it returns a bare float), so the mismatch guard Money normally
            # provides (see require_same_currency) has to be checked here
            # instead — a dual-listed company can report financials in a
            # different currency than the one its shares trade in.
            draw_no_data(ax)
            return

        # Book value per share is only reported at statement-cadence (quarterly
        # or annual) dates, while price trades daily — there is rarely an exact
        # date match. Pair each statement date with its nearest price quote
        # instead of the exact-date join `resolve()` uses for same-cadence
        # metrics (e.g. margins).
        dates = []
        values = []
        for point in book_value.points:
            if point.value == 0:
                continue
            nearest_price = _nearest_price(price_points, point.date)
            dates.append(point.date)
            values.append(nearest_price / point.value)

        if not values:
            draw_no_data(ax)
            return

        render_ratio_line(ax, dates, values, "P/B")
        ax.set_ylabel("Price / Book (x)")
        ax.legend(fontsize=7, loc="upper left")


def _nearest_price(price_points: list[Point], target: date) -> float:
    closest = min(price_points, key=lambda p: abs((p.date - target).days))
    return closest.value.value
