from investigraph.sources.currency import AGOROT_CODE, map_currency
from investigraph.template.models import Currency


def test_agorot_maps_to_ils():
    # The single point where the agorot decision is made: "ILA" is a TASE
    # quote in 1/100 shekel, so it is ILS to the template — the adapter has
    # already divided the value by 100 by the time it tags the point.
    assert AGOROT_CODE == "ILA"
    assert map_currency("ILA") is Currency.ILS


def test_shekel_maps_to_ils():
    assert map_currency("ILS") is Currency.ILS


def test_dollar_maps_to_usd():
    assert map_currency("USD") is Currency.USD


def test_unknown_code_returns_none_rather_than_guessing():
    # A currency we can't identify must degrade the metric to "no data", never
    # fall back to a default — a mislabeled ₪/$ series is worse than a blank one.
    assert map_currency("EUR") is None


def test_missing_code_returns_none():
    assert map_currency(None) is None
    assert map_currency("") is None
