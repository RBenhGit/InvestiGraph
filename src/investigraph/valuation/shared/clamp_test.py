from investigraph.valuation.shared.clamp import (
    GROWTH_RATE_FLOOR_PERCENT,
    clamp_growth_rate,
)


def test_leaves_a_value_inside_the_band_unchanged():
    assert clamp_growth_rate(10) == 10


def test_floors_a_value_below_the_floor():
    assert clamp_growth_rate(-20) == GROWTH_RATE_FLOOR_PERCENT


def test_leaves_a_high_value_unchanged_no_ceiling():
    assert clamp_growth_rate(40) == 40


def test_leaves_the_exact_floor_boundary_unchanged():
    assert clamp_growth_rate(GROWTH_RATE_FLOOR_PERCENT) == GROWTH_RATE_FLOOR_PERCENT
