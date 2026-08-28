from datetime import date

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from financial_charts.charts.builtins._test_helpers import fundamentals_with
from financial_charts.charts.builtins.valuation import ValuationChart
from financial_charts.template.models import Currency, MetricSeries, Money, Point, Unit


def _price_series(
    points: list[tuple[date, float]], currency: Currency = Currency.USD
) -> MetricSeries:
    return MetricSeries(
        metric_id="price",
        points=[
            Point(date=d, value=Money(value=v, currency=currency, scale=Unit.ONES))
            for d, v in points
        ],
        available=True,
    )


def _equity_series(points: list[tuple[date, float]]) -> MetricSeries:
    return MetricSeries(
        metric_id="total_equity",
        points=[
            Point(
                date=d,
                value=Money(value=v, currency=Currency.USD, scale=Unit.MILLIONS),
            )
            for d, v in points
        ],
        available=True,
    )


def _share_count_series(points: list[tuple[date, float]]) -> MetricSeries:
    return MetricSeries(
        metric_id="shares_outstanding",
        points=[Point(date=d, value=v) for d, v in points],
        available=True,
    )


def test_declares_price_equity_and_shares_as_required():
    assert ValuationChart().required_metrics == [
        "price",
        "total_equity",
        "shares_outstanding",
    ]


def test_pairs_each_statement_date_with_its_nearest_price_quote():
    # Price trades daily; book value per share only exists at the one
    # quarterly statement date. The chart must still produce a P/B point by
    # using the closest price quote rather than requiring an exact match.
    fundamentals = fundamentals_with(
        {
            "price": _price_series(
                [
                    (date(2020, 3, 28), 90.0),
                    (date(2020, 4, 2), 100.0),
                    (date(2020, 4, 10), 110.0),
                ]
            ),
            "total_equity": _equity_series([(date(2020, 3, 31), 200)]),
            "shares_outstanding": _share_count_series([(date(2020, 3, 31), 100.0)]),
        }
    )
    fig, ax = plt.subplots()

    ValuationChart().render(ax, fundamentals)

    # book value/share = $200,000,000 / 100 = $2,000,000/share; nearest
    # quote to 2020-03-31 is 2020-04-02's $100.
    line = ax.get_lines()[0]
    assert list(line.get_ydata()) == [100.0 / 2_000_000]
    plt.close(fig)


def test_falls_back_to_no_data_on_currency_mismatch():
    # A dual-listed company can report financials in a different currency
    # than the one its shares trade in. BOOK_VALUE_PER_SHARE discards its
    # Money currency tag (it returns a bare float), so the chart must check
    # this itself rather than silently computing a nonsensical P/B.
    fundamentals = fundamentals_with(
        {
            "price": _price_series([(date(2020, 3, 31), 100.0)], currency=Currency.ILS),
            "total_equity": _equity_series([(date(2020, 3, 31), 200)]),
            "shares_outstanding": _share_count_series([(date(2020, 3, 31), 100.0)]),
        }
    )
    fig, ax = plt.subplots()

    ValuationChart().render(ax, fundamentals)

    assert ax.get_lines() == []
    texts = [t.get_text() for t in ax.texts]
    assert "No Data" in texts
    plt.close(fig)


def test_falls_back_to_no_data_when_book_value_is_unavailable():
    fundamentals = fundamentals_with(
        {
            "price": _price_series([(date(2020, 1, 1), 100.0)]),
            "total_equity": MetricSeries(
                metric_id="total_equity", points=[], available=False
            ),
            "shares_outstanding": _share_count_series([(date(2020, 1, 1), 100.0)]),
        }
    )
    fig, ax = plt.subplots()

    ValuationChart().render(ax, fundamentals)

    assert ax.get_lines() == []
    texts = [t.get_text() for t in ax.texts]
    assert "No Data" in texts
    plt.close(fig)
