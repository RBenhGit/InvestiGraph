from unittest.mock import patch

import pytest

from financial_charts.sources.base import MissingCredentials
from financial_charts.sources.registry import (
    get_capability,
    get_source,
    registered_sources,
)
from financial_charts.sources.twelvedata.adapter import TwelveDataAdapter
from financial_charts.sources.yfinance.adapter import YFinanceAdapter
from financial_charts.template.models import Period


def test_resolves_yfinance():
    assert isinstance(get_source("yfinance"), YFinanceAdapter)


def test_resolves_twelvedata_with_credentials():
    with patch.dict("os.environ", {"TWELVEDATA_API_KEY": "test-key"}):
        assert isinstance(get_source("twelvedata"), TwelveDataAdapter)


def test_twelvedata_without_credentials_raises_missing_credentials():
    with (
        patch("financial_charts.sources.twelvedata.adapter.load_dotenv"),
        patch.dict("os.environ", {}, clear=True),
    ):
        with pytest.raises(MissingCredentials):
            get_source("twelvedata")


def test_unknown_source_raises_key_error():
    with pytest.raises(KeyError):
        get_source("not-a-real-source")


def test_registered_sources_lists_all():
    assert registered_sources() == ["twelvedata", "yfinance"]


def test_every_registered_source_has_a_capability():
    # Guards against a source being registered without a matching capability
    # declaration (get_source and get_capability share one registration table,
    # so this can't drift, but the invariant is worth pinning explicitly).
    for name in registered_sources():
        get_capability(name)


def test_get_capability_twelvedata_requires_no_credentials():
    with patch.dict("os.environ", {}, clear=True):
        capability = get_capability("twelvedata")
    assert capability.max_history[Period.ANNUAL] == 10


def test_get_capability_yfinance_matches_declared_metrics():
    capability = get_capability("yfinance")
    assert "price" in capability.metrics
    assert capability.max_history[Period.ANNUAL] == 4


def test_get_capability_unknown_source_raises_key_error():
    with pytest.raises(KeyError):
        get_capability("not-a-real-source")
