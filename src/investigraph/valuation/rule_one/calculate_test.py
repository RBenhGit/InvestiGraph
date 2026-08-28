import pytest

from investigraph.valuation.rule_one.calculate import calculate_rule_one_value
from investigraph.valuation.shared.types import ValuationErr


def test_collapses_to_eps_times_exit_pe_when_growth_equals_required_return():
    # (1+g)^N cancels (1+r)^N when g == r.
    result = calculate_rule_one_value(10, 10, 15, 10, 10)
    assert result.ok is True
    assert result.fair_value == pytest.approx(150, abs=1e-6)


def test_discounts_away_from_naive_eps_times_exit_pe_when_growth_ne_required_return():
    result = calculate_rule_one_value(10, 15, 15, 10, 10)
    assert result.ok is True
    assert result.fair_value != pytest.approx(150, abs=0.5)
    assert result.fair_value == pytest.approx(233.96064555028698, abs=1e-6)


def test_returns_missing_eps_when_eps_is_missing():
    result = calculate_rule_one_value(None, 10, 15, 10, 10)
    assert result == ValuationErr(error="MISSING_EPS")


def test_returns_negative_or_zero_eps_when_eps_lte_0():
    result = calculate_rule_one_value(0, 10, 15, 10, 10)
    assert result == ValuationErr(error="NEGATIVE_OR_ZERO_EPS")


def test_returns_missing_growth_rate_when_growth_is_missing():
    result = calculate_rule_one_value(10, None, 15, 10, 10)
    assert result == ValuationErr(error="MISSING_GROWTH_RATE")


def test_returns_invalid_exit_pe_when_exit_pe_multiple_is_not_positive():
    result = calculate_rule_one_value(10, 10, 0, 10, 10)
    assert result == ValuationErr(error="INVALID_EXIT_PE")


def test_returns_invalid_required_return_when_not_positive():
    result = calculate_rule_one_value(10, 10, 15, 0, 10)
    assert result == ValuationErr(error="INVALID_REQUIRED_RETURN")


def test_returns_invalid_years_when_not_a_positive_integer():
    result = calculate_rule_one_value(10, 10, 15, 10, 0)
    assert result == ValuationErr(error="INVALID_YEARS")


def test_applies_margin_of_safety_discount_correctly_when_mos_percent_gt_0():
    # With g = 10, r = 10, sticker price is 150.
    # With 25% MoS, fair_value should be 150 * 0.75 = 112.5
    result = calculate_rule_one_value(10, 10, 15, 10, 10, 25)
    assert result.ok is True
    assert result.fair_value == pytest.approx(112.5, abs=1e-6)
    assert result.inputs.mos_percent == 25
    assert result.intermediate["sticker_price"] == pytest.approx(150, abs=1e-6)
    assert result.intermediate["mos_price"] == pytest.approx(112.5, abs=1e-6)


def test_returns_invalid_mos_when_mos_percent_negative_or_gte_100():
    assert calculate_rule_one_value(10, 10, 15, 10, 10, -5) == ValuationErr(
        error="INVALID_MOS"
    )
    assert calculate_rule_one_value(10, 10, 15, 10, 10, 100) == ValuationErr(
        error="INVALID_MOS"
    )
