import math
from datetime import date

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from investigraph.charts.builtins._test_helpers import (
    fundamentals_with,
    money_series,
)
from investigraph.charts.builtins.pe_ratio import PERatioChart
from investigraph.template.models import (
    Currency,
    MetricSeries,
    Money,
    Period,
    Point,
    Unit,
)


def test_declares_price_and_eps_as_required():
    assert PERatioChart().required_metrics == ["price", "eps"]


def test_title_reflects_trailing_twelve_month_basis():
    assert PERatioChart().title == "P/E (TTM)"


def test_renders_a_daily_price_over_ttm_eps_line():
    fundamentals = fundamentals_with(
        {
            "price": money_series("price", [100.0, 200.0]),
            "eps": money_series("eps", [4.0, 5.0]),
        }
    )
    fig, ax = plt.subplots()

    PERatioChart().render(ax, fundamentals)

    assert len(ax.lines) == 1
    assert list(ax.lines[0].get_ydata()) == [100.0 / 4.0, 200.0 / 5.0]
    plt.close(fig)


def test_falls_back_to_no_data_on_non_positive_eps():
    fundamentals = fundamentals_with(
        {
            "price": money_series("price", [100.0]),
            "eps": money_series("eps", [0.0]),
        }
    )
    fig, ax = plt.subplots()

    PERatioChart().render(ax, fundamentals)

    texts = [t.get_text() for t in ax.texts]
    assert "No Data" in texts
    plt.close(fig)


def test_no_lookahead_skips_price_dates_before_the_first_eps():
    price = MetricSeries(
        metric_id="price",
        points=[
            Point(
                date=date(2019, 1, 1),
                value=Money(value=100, currency=Currency.USD, scale=Unit.ONES),
            ),
            Point(
                date=date(2020, 1, 1),
                value=Money(value=110, currency=Currency.USD, scale=Unit.ONES),
            ),
        ],
        available=True,
    )
    eps = MetricSeries(
        metric_id="eps",
        points=[
            Point(
                date=date(2020, 1, 1),
                value=Money(value=5, currency=Currency.USD, scale=Unit.ONES),
            ),
        ],
        available=True,
    )
    fundamentals = fundamentals_with({"price": price, "eps": eps})
    fig, ax = plt.subplots()

    PERatioChart().render(ax, fundamentals)

    assert list(ax.lines[0].get_xdata()) == [date(2020, 1, 1)]
    plt.close(fig)


def test_a_loss_year_breaks_the_line_instead_of_interpolating_through_it():
    # A single loss year's non-positive TTM EPS must not vanish from the
    # series and let matplotlib draw a straight line connecting the
    # surrounding profitable years' P/E values *through* the loss year — the
    # affected daily price dates must plot as NaN, breaking the line there.
    eps = MetricSeries(
        metric_id="eps",
        points=[
            Point(
                date=date(2020, 12, 31),
                value=Money(value=5.0, currency=Currency.USD, scale=Unit.ONES),
            ),
            Point(
                date=date(2021, 12, 31),
                value=Money(value=-2.0, currency=Currency.USD, scale=Unit.ONES),
            ),
            Point(
                date=date(2022, 12, 31),
                value=Money(value=4.0, currency=Currency.USD, scale=Unit.ONES),
            ),
        ],
        available=True,
    )
    price = MetricSeries(
        metric_id="price",
        points=[
            # As of 2022-06-01, the most recent trailing EPS is FY2021's loss
            # (reported 2021-12-31); as of 2023-06-01, it's FY2022's profit
            # (reported 2022-12-31).
            Point(
                date=date(2022, 6, 1),
                value=Money(value=100.0, currency=Currency.USD, scale=Unit.ONES),
            ),
            Point(
                date=date(2023, 6, 1),
                value=Money(value=100.0, currency=Currency.USD, scale=Unit.ONES),
            ),
        ],
        available=True,
    )
    fundamentals = fundamentals_with({"price": price, "eps": eps})
    fig, ax = plt.subplots()

    PERatioChart().render(ax, fundamentals)

    values = list(ax.lines[0].get_ydata())
    assert len(values) == 2
    assert math.isnan(values[0])  # 2022-06-01: trailing EPS is the loss year
    assert values[1] == 25.0  # 2023-06-01: trailing EPS is FY2022's 4.0
    plt.close(fig)


def test_quarterly_ttm_end_to_end():
    quarter_ends = [
        date(2022, 3, 31),
        date(2022, 6, 30),
        date(2022, 9, 30),
        date(2022, 12, 31),
    ]
    eps = MetricSeries(
        metric_id="eps",
        points=[
            Point(
                date=d, value=Money(value=1.0, currency=Currency.USD, scale=Unit.ONES)
            )
            for d in quarter_ends
        ],
        available=True,
    )
    price = MetricSeries(
        metric_id="price",
        points=[
            Point(
                date=date(2022, 12, 31),
                value=Money(value=200, currency=Currency.USD, scale=Unit.ONES),
            )
        ],
        available=True,
    )
    fundamentals = fundamentals_with(
        {"price": price, "eps": eps}, period=Period.QUARTERLY
    )
    fig, ax = plt.subplots()

    PERatioChart().render(ax, fundamentals)

    # TTM EPS across the 4 quarters = 4.0, price 200 -> P/E 50.0
    assert list(ax.lines[0].get_ydata()) == [50.0]
    plt.close(fig)
