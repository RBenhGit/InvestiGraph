from datetime import date

import pytest

from financial_charts.template.derived import (
    BOOK_VALUE_PER_SHARE,
    CURRENT_RATIO,
    DEBT_TO_EQUITY,
    FCF_MARGIN,
    ROCE,
    ROIC,
    DerivedMetric,
    ratio,
    resolve,
)
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


def _fundamentals(series: dict[str, MetricSeries]) -> CompanyFundamentals:
    return CompanyFundamentals(
        ticker="TEST",
        market=Market.US,
        currency=Currency.USD,
        period=Period.ANNUAL,
        range="5y",
        series=series,
    )


def _money_series(
    metric_id: str,
    values_by_date: list[tuple[date, float]],
    scale: Unit = Unit.ONES,
    currency: Currency = Currency.USD,
) -> MetricSeries:
    return MetricSeries(
        metric_id=metric_id,
        points=[
            Point(date=d, value=Money(value=v, currency=currency, scale=scale))
            for d, v in values_by_date
        ],
        available=True,
    )


def test_ratio_uses_base_units_so_mismatched_scales_cancel_correctly():
    numerator = Money(value=200, currency=Currency.USD, scale=Unit.MILLIONS)
    denominator = Money(value=1_000, currency=Currency.USD, scale=Unit.ONES)

    assert ratio(numerator, denominator) == pytest.approx(200_000)


def test_ratio_naive_raw_value_division_would_be_wrong():
    # Guards the exact trap Money exists to prevent: dividing .value directly
    # (200 / 1000 = 0.2) is off by a factor of a million from the true ratio.
    numerator = Money(value=200, currency=Currency.USD, scale=Unit.MILLIONS)
    denominator = Money(value=1_000, currency=Currency.USD, scale=Unit.ONES)

    naive = numerator.value / denominator.value
    assert ratio(numerator, denominator) != pytest.approx(naive)


def test_ratio_rejects_mismatched_currency():
    numerator = Money(value=1, currency=Currency.USD, scale=Unit.ONES)
    denominator = Money(value=1, currency=Currency.ILS, scale=Unit.ONES)

    with pytest.raises(ValueError):
        ratio(numerator, denominator)


def test_resolve_computes_common_dates_only():
    fundamentals = _fundamentals(
        {
            "free_cash_flow": _money_series(
                "free_cash_flow",
                [(date(2020, 1, 1), 100), (date(2021, 1, 1), 150)],
                scale=Unit.MILLIONS,
            ),
            "revenue": _money_series(
                "revenue",
                [(date(2020, 1, 1), 1000), (date(2022, 1, 1), 1200)],
                scale=Unit.MILLIONS,
            ),
        }
    )

    series = resolve(fundamentals, FCF_MARGIN)

    assert [p.date for p in series.points] == [date(2020, 1, 1)]
    assert series.points[0].value == pytest.approx(0.1)
    assert series.available is True


def test_resolve_unavailable_when_an_input_metric_is_missing():
    fundamentals = _fundamentals(
        {"free_cash_flow": _money_series("free_cash_flow", [(date(2020, 1, 1), 100)])}
    )

    series = resolve(fundamentals, FCF_MARGIN)

    assert series.available is False
    assert series.points == []


def test_resolve_unavailable_when_an_input_metric_is_marked_unavailable():
    fundamentals = _fundamentals(
        {
            "free_cash_flow": _money_series(
                "free_cash_flow", [(date(2020, 1, 1), 100)]
            ),
            "revenue": MetricSeries(metric_id="revenue", points=[], available=False),
        }
    )

    series = resolve(fundamentals, FCF_MARGIN)

    assert series.available is False


def test_resolve_skips_a_point_with_zero_denominator_without_crashing():
    fundamentals = _fundamentals(
        {
            "free_cash_flow": _money_series(
                "free_cash_flow",
                [(date(2020, 1, 1), 100), (date(2021, 1, 1), 50)],
            ),
            "revenue": _money_series(
                "revenue",
                [(date(2020, 1, 1), 0), (date(2021, 1, 1), 500)],
            ),
        }
    )

    series = resolve(fundamentals, FCF_MARGIN)

    assert [p.date for p in series.points] == [date(2021, 1, 1)]


def test_custom_derived_metric_with_arbitrary_compute():
    doubled = DerivedMetric(
        metric_id="double_price",
        title="Double Price",
        inputs=("price",),
        compute=lambda money: money.as_base_units() * 2,
    )
    fundamentals = _fundamentals(
        {"price": _money_series("price", [(date(2020, 1, 1), 10)])}
    )

    series = resolve(fundamentals, doubled)

    assert series.points[0].value == 20


def test_resolve_unavailable_for_a_derived_metric_with_no_inputs():
    no_inputs = DerivedMetric(
        metric_id="constant",
        title="Constant",
        inputs=(),
        compute=lambda: 1.0,
    )

    series = resolve(_fundamentals({}), no_inputs)

    assert series.available is False
    assert series.points == []


def test_resolve_skips_a_point_whose_compute_raises_value_error():
    # A `compute` that surfaces a ValueError (e.g. ratio()'s currency-mismatch
    # guard) must degrade that one point, not propagate and crash the caller —
    # the same contract as the ZeroDivisionError case.
    raises_on_first_date = DerivedMetric(
        metric_id="flaky",
        title="Flaky",
        inputs=("price",),
        compute=lambda money: (
            (_ for _ in ()).throw(ValueError("bad"))
            if money.value == 10
            else money.value
        ),
    )
    fundamentals = _fundamentals(
        {
            "price": _money_series(
                "price",
                [(date(2020, 1, 1), 10), (date(2021, 1, 1), 20)],
            )
        }
    )

    series = resolve(fundamentals, raises_on_first_date)

    assert [p.date for p in series.points] == [date(2021, 1, 1)]


def test_current_ratio_divides_current_assets_by_current_liabilities():
    fundamentals = _fundamentals(
        {
            "total_current_assets": _money_series(
                "total_current_assets", [(date(2020, 1, 1), 200)]
            ),
            "total_current_liabilities": _money_series(
                "total_current_liabilities", [(date(2020, 1, 1), 100)]
            ),
        }
    )

    series = resolve(fundamentals, CURRENT_RATIO)

    assert series.points[0].value == pytest.approx(2.0)


def test_debt_to_equity_divides_total_debt_by_total_equity():
    fundamentals = _fundamentals(
        {
            "total_debt": _money_series("total_debt", [(date(2020, 1, 1), 50)]),
            "total_equity": _money_series("total_equity", [(date(2020, 1, 1), 200)]),
        }
    )

    series = resolve(fundamentals, DEBT_TO_EQUITY)

    assert series.points[0].value == pytest.approx(0.25)


def test_roce_divides_ebit_by_capital_employed():
    fundamentals = _fundamentals(
        {
            "ebit": _money_series("ebit", [(date(2020, 1, 1), 20)]),
            "total_assets": _money_series("total_assets", [(date(2020, 1, 1), 300)]),
            "total_current_liabilities": _money_series(
                "total_current_liabilities", [(date(2020, 1, 1), 100)]
            ),
        }
    )

    series = resolve(fundamentals, ROCE)

    # 20 / (300 - 100) = 0.1
    assert series.points[0].value == pytest.approx(0.1)


def test_book_value_per_share_divides_equity_by_share_count():
    fundamentals = _fundamentals(
        {
            "total_equity": _money_series(
                "total_equity", [(date(2020, 1, 1), 200)], scale=Unit.MILLIONS
            ),
            "shares_outstanding": MetricSeries(
                metric_id="shares_outstanding",
                points=[Point(date=date(2020, 1, 1), value=100.0)],
                available=True,
            ),
        }
    )

    series = resolve(fundamentals, BOOK_VALUE_PER_SHARE)

    # $200,000,000 equity / 100 shares = $2,000,000/share
    assert series.points[0].value == pytest.approx(2_000_000)


def test_roic_divides_net_income_by_invested_capital():
    fundamentals = _fundamentals(
        {
            "net_income": _money_series("net_income", [(date(2020, 1, 1), 15)]),
            "total_debt": _money_series("total_debt", [(date(2020, 1, 1), 50)]),
            "total_equity": _money_series("total_equity", [(date(2020, 1, 1), 200)]),
            "cash_and_equivalents": _money_series(
                "cash_and_equivalents", [(date(2020, 1, 1), 50)]
            ),
        }
    )

    series = resolve(fundamentals, ROIC)

    # 15 / (50 + 200 - 50) = 0.075
    assert series.points[0].value == pytest.approx(0.075)


def test_resolve_skips_a_point_whose_compute_raises_attribute_or_type_error():
    # A `compute` that assumes every input is a Money (e.g. calls
    # .as_base_units()) must degrade a bare-float point, not crash the whole
    # dashboard render.
    assumes_money = DerivedMetric(
        metric_id="flaky",
        title="Flaky",
        inputs=("price",),
        compute=lambda value: value.as_base_units(),
    )
    fundamentals = _fundamentals(
        {
            "price": MetricSeries(
                metric_id="price",
                points=[
                    Point(date=date(2020, 1, 1), value=10.0),
                    Point(
                        date=date(2021, 1, 1),
                        value=Money(value=10, currency=Currency.USD, scale=Unit.ONES),
                    ),
                ],
            )
        }
    )

    series = resolve(fundamentals, assumes_money)

    assert [p.date for p in series.points] == [date(2021, 1, 1)]
