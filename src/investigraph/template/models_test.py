from datetime import date

import pytest

from financial_charts.template.models import (
    CompanyFundamentals,
    Currency,
    Market,
    MetricSeries,
    Money,
    Period,
    Point,
    Unit,
)


def test_money_to_rescales_preserving_amount():
    price_in_agorot = Money(value=12345, currency=Currency.ILS, scale=Unit.ONES)
    price_in_millions = price_in_agorot.to(Unit.MILLIONS)

    assert price_in_millions.value == pytest.approx(12345 / 1_000_000)
    assert price_in_millions.currency == Currency.ILS


def test_money_add_same_currency_rescales_correctly():
    revenue_q1 = Money(value=1.5, currency=Currency.ILS, scale=Unit.MILLIONS)
    revenue_q2 = Money(value=500_000, currency=Currency.ILS, scale=Unit.ONES)

    total = revenue_q1 + revenue_q2

    assert total.scale == Unit.MILLIONS
    assert total.value == pytest.approx(2.0)


def test_money_add_different_currency_raises():
    usd_amount = Money(value=100, currency=Currency.USD, scale=Unit.ONES)
    ils_amount = Money(value=100, currency=Currency.ILS, scale=Unit.ONES)

    with pytest.raises(ValueError, match="different currencies"):
        usd_amount + ils_amount


def test_tase_agorot_price_converts_to_correct_shekel_value():
    # A known TASE price quote: 1523 agorot == 15.23 NIS.
    agorot_price = Money(value=1523, currency=Currency.ILS, scale=Unit.ONES)

    shekels = agorot_price.as_base_units() / 100

    assert shekels == pytest.approx(15.23)


def test_money_is_immutable():
    m = Money(value=1, currency=Currency.USD, scale=Unit.ONES)
    with pytest.raises(Exception):
        m.value = 2


def test_metric_series_with_empty_points_is_forced_unavailable():
    series = MetricSeries(metric_id="revenue", points=[], available=True)

    assert series.available is False


def test_metric_series_with_points_stays_available():
    series = MetricSeries(
        metric_id="revenue",
        points=[
            Point(
                date=date(2020, 1, 1),
                value=Money(value=1, currency=Currency.USD, scale=Unit.ONES),
            )
        ],
        available=True,
    )

    assert series.available is True


def test_metric_series_rejects_mixed_currency_points():
    with pytest.raises(ValueError, match="inconsistent Money currency/scale"):
        MetricSeries(
            metric_id="revenue",
            points=[
                Point(
                    date=date(2020, 1, 1),
                    value=Money(value=1, currency=Currency.USD, scale=Unit.ONES),
                ),
                Point(
                    date=date(2021, 1, 1),
                    value=Money(value=1, currency=Currency.ILS, scale=Unit.ONES),
                ),
            ],
        )


def test_metric_series_rejects_mixed_scale_points():
    with pytest.raises(ValueError, match="inconsistent Money currency/scale"):
        MetricSeries(
            metric_id="revenue",
            points=[
                Point(
                    date=date(2020, 1, 1),
                    value=Money(value=1, currency=Currency.USD, scale=Unit.ONES),
                ),
                Point(
                    date=date(2021, 1, 1),
                    value=Money(value=1, currency=Currency.USD, scale=Unit.MILLIONS),
                ),
            ],
        )


def test_company_fundamentals_allows_a_series_in_a_different_currency_than_display():
    # Real case: a TASE-listed multinational (e.g. Teva) can trade in ILS
    # (agorot) while its financial statements are reported in USD. The
    # top-level `currency` labels price/display; it must not force every
    # series to match, or a legitimate dual-currency company fails to render.
    series = MetricSeries(
        metric_id="revenue",
        points=[
            Point(
                date=date(2020, 1, 1),
                value=Money(value=1, currency=Currency.USD, scale=Unit.ONES),
            )
        ],
    )

    fundamentals = CompanyFundamentals(
        ticker="TEVA.TA",
        market=Market.TASE,
        currency=Currency.ILS,
        period=Period.ANNUAL,
        range="5y",
        series={"revenue": series},
    )

    assert fundamentals.series["revenue"].points[0].value.currency == Currency.USD
