from unittest.mock import patch

from financial_charts.config import data_source_name


def test_defaults_to_yfinance():
    with patch.dict("os.environ", {}, clear=True):
        assert data_source_name() == "yfinance"


def test_reads_data_source_env_var():
    with patch.dict("os.environ", {"DATA_SOURCE": "twelvedata"}):
        assert data_source_name() == "twelvedata"


def test_strips_surrounding_whitespace():
    with patch.dict("os.environ", {"DATA_SOURCE": " twelvedata "}):
        assert data_source_name() == "twelvedata"
