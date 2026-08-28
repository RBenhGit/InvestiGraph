import pytest

from financial_charts.sources.base import Capability, UnsupportedPeriod
from financial_charts.sources.validation import check_request, require_supported_period
from financial_charts.template.models import Market, Period


def _capability(**overrides) -> Capability:
    defaults = dict(
        markets={Market.US},
        periods={Period.ANNUAL},
        max_history={Period.ANNUAL: 4},
        metrics={"revenue"},
    )
    defaults.update(overrides)
    return Capability(**defaults)


def test_request_within_capability_has_no_limits():
    cap = _capability(max_history={Period.ANNUAL: 10})
    assert check_request(cap, Market.US, Period.ANNUAL, "10y") == []


def test_free_tier_4y_history_flags_10y_request():
    cap = _capability(max_history={Period.ANNUAL: 4})
    limits = check_request(cap, Market.US, Period.ANNUAL, "10y")
    assert len(limits) == 1
    assert "4y" in limits[0]
    assert "10y" in limits[0]


def test_unsupported_market_is_flagged():
    cap = _capability(markets={Market.US})
    limits = check_request(cap, Market.TASE, Period.ANNUAL, "1y")
    assert any("TASE" in limit for limit in limits)


def test_unsupported_period_is_flagged_and_skips_history_check():
    cap = _capability(periods={Period.ANNUAL}, max_history={Period.ANNUAL: 4})
    limits = check_request(cap, Market.US, Period.QUARTERLY, "1y")
    assert len(limits) == 1
    assert "quarterly" in limits[0]


def test_unrecognized_range_is_explicitly_flagged():
    cap = _capability(max_history={Period.ANNUAL: 4})
    limits = check_request(cap, Market.US, Period.ANNUAL, "8y")
    assert len(limits) == 1
    assert "8y" in limits[0]
    assert "unrecognized" in limits[0]


def test_require_supported_period_raises_for_unsupported_period():
    cap = _capability(periods={Period.ANNUAL})
    with pytest.raises(UnsupportedPeriod, match="ttm"):
        require_supported_period(cap, Period.TTM)


def test_require_supported_period_passes_for_supported_period():
    cap = _capability(periods={Period.ANNUAL})
    require_supported_period(cap, Period.ANNUAL)  # does not raise
