import math
from datetime import date

import pytest

from investigraph.charts.fit import fit_exponential, fit_linear

_D0 = date(2020, 1, 1)
_D1 = date(2021, 1, 1)
_D2 = date(2022, 1, 1)
_D3 = date(2023, 1, 1)


def test_fit_linear_recovers_an_exact_line():
    # y = 10 + 5*years, sampled at ~yearly points -- an exact line should
    # fit with (near) zero residual and a slope of 5/year.
    dates = [_D0, _D1, _D2, _D3]
    values = [10.0, 15.0, 20.0, 25.0]

    result = fit_linear(dates, values)

    assert result is not None
    assert result.rate == pytest.approx(5.0, abs=0.01)
    for fitted, actual in zip(result.fitted_values, values):
        assert fitted == pytest.approx(actual, abs=0.1)


def test_fit_linear_handles_negative_and_zero_values():
    # A loss-making net-income series should still get a straight-line fit --
    # unlike the exponential fit, a line is defined for any real values.
    dates = [_D0, _D1, _D2]
    values = [-10.0, 0.0, 10.0]

    result = fit_linear(dates, values)

    assert result is not None
    assert result.rate > 0


def test_fit_linear_returns_none_for_fewer_than_two_points():
    assert fit_linear([_D0], [10.0]) is None
    assert fit_linear([], []) is None


def test_fit_exponential_recovers_a_known_growth_rate():
    # y = 100 * 1.10^years -- a 10%/yr exponential series, sampled yearly.
    dates = [_D0, _D1, _D2, _D3]
    values = [100.0 * (1.10**i) for i in range(4)]

    result = fit_exponential(dates, values)

    assert result is not None
    assert result.rate == pytest.approx(0.10, abs=0.005)
    for fitted, actual in zip(result.fitted_values, values):
        assert fitted == pytest.approx(actual, rel=0.01)


def test_fit_exponential_returns_none_for_a_non_positive_value():
    # A real logarithm doesn't exist for a zero/negative value (e.g. a
    # loss-making year's net income) -- this must degrade to "no fit"
    # rather than crash or silently skip just that one point.
    dates = [_D0, _D1, _D2]
    values = [10.0, -5.0, 20.0]

    assert fit_exponential(dates, values) is None

    zero_values = [10.0, 0.0, 20.0]
    assert fit_exponential(dates, zero_values) is None


def test_fit_exponential_returns_none_for_fewer_than_two_points():
    assert fit_exponential([_D0], [10.0]) is None
    assert fit_exponential([], []) is None


def test_fit_linear_returns_none_when_every_date_is_identical():
    assert fit_linear([_D0, _D0, _D0], [1.0, 2.0, 3.0]) is None


def test_fit_exponential_returns_none_when_every_date_is_identical():
    assert fit_exponential([_D0, _D0, _D0], [1.0, 2.0, 3.0]) is None


def test_fit_results_contain_no_nan_or_inf():
    dates = [_D0, _D1, _D2, _D3]
    values = [50.0, 60.0, 55.0, 70.0]

    linear = fit_linear(dates, values)
    exponential = fit_exponential(dates, values)

    assert linear is not None
    assert exponential is not None
    assert all(math.isfinite(v) for v in linear.fitted_values)
    assert math.isfinite(linear.rate)
    assert all(math.isfinite(v) for v in exponential.fitted_values)
    assert math.isfinite(exponential.rate)
