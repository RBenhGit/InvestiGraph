import pytest

from investigraph.valuation.lynch.calculate import calculate_lynch_value
from investigraph.valuation.shared.types import ValuationErr


def test_computes_fair_value_eps_times_growth():
    result = calculate_lynch_value(5, 15)
    assert result.ok is True
    assert result.fair_value == 75


def test_returns_negative_or_zero_eps_for_eps_0():
    result = calculate_lynch_value(0, 15)
    assert result == ValuationErr(error="NEGATIVE_OR_ZERO_EPS")


def test_returns_negative_or_zero_eps_for_eps_negative_2():
    result = calculate_lynch_value(-2, 15)
    assert result == ValuationErr(error="NEGATIVE_OR_ZERO_EPS")


def test_returns_missing_growth_rate_when_growth_is_missing():
    result = calculate_lynch_value(5, None)
    assert result == ValuationErr(error="MISSING_GROWTH_RATE")


def test_returns_missing_eps_when_eps_is_missing():
    result = calculate_lynch_value(None, 15)
    assert result == ValuationErr(error="MISSING_EPS")


def test_does_not_clamp_high_growth_40_proving_no_maximum_ceiling():
    result = calculate_lynch_value(5, 40)
    assert result.ok is True
    assert result.fair_value == 200
    assert result.inputs.growth_rate_percent_clamped == 40
    assert result.inputs.growth_rate_percent_raw == 40


# Regression, found by running the two methods over 26 real cached tickers: ABBV has a
# genuinely negative 3y EPS CAGR (-29.03%, clamped to -5%), and `eps * growth_percent` then
# produced a fair value of -17.69 -- a NEGATIVE DOLLAR AMOUNT returned as ok=True, which both
# the CLI and the web UI rendered as a real valuation ("Method A (Lynch) fair value: -17.69",
# and a -108.85% "downside" in the price banner). The Lynch/PEG heuristic is only defined for
# positive growth; a shrinking company has no meaningful PEG fair value, so this is an error,
# not a small number. Rule #1 is unaffected -- compounding a positive EPS at a negative rate
# shrinks it without ever flipping the sign (ABBV still yields a sane 7.86 there).
def test_returns_negative_growth_rate_instead_of_a_negative_dollar_fair_value():
    result = calculate_lynch_value(3.538947, -29.0294)
    assert result.ok is False
    assert result.error == "NEGATIVE_GROWTH_RATE"


def test_also_rejects_a_growth_rate_of_exactly_zero():
    result = calculate_lynch_value(5, 0)
    assert result.ok is False
    assert result.error == "NEGATIVE_GROWTH_RATE"


def test_still_values_a_normally_growing_company():
    result = calculate_lynch_value(5, 12)
    assert result.ok is True
    assert result.fair_value == pytest.approx(60, abs=1e-10)
