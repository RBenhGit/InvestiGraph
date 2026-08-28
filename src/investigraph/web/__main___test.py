from unittest.mock import MagicMock, patch

from financial_charts.web.__main__ import main


def test_host_defaults_to_localhost_not_all_interfaces():
    mock_app = MagicMock()
    with patch("financial_charts.web.__main__.create_app", return_value=mock_app):
        main([])

    mock_app.run.assert_called_once()
    assert mock_app.run.call_args.kwargs["host"] == "127.0.0.1"


def test_host_can_be_overridden():
    mock_app = MagicMock()
    with patch("financial_charts.web.__main__.create_app", return_value=mock_app):
        main(["--host", "0.0.0.0"])

    assert mock_app.run.call_args.kwargs["host"] == "0.0.0.0"
