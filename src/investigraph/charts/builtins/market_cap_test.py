import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from investigraph.charts.builtins._test_helpers import (
    fundamentals_with,
    money_series,
    ratio_series,
    unavailable_series,
)
from investigraph.charts.builtins.market_cap import MarketCapChart


def test_declares_price_and_shares_outstanding_as_required():
    assert MarketCapChart().required_metrics == ["price", "shares_outstanding"]


def test_renders_price_times_as_of_shares_outstanding_as_a_line():
    fundamentals = fundamentals_with(
        {
            "price": money_series("price", [10.0, 20.0]),
            "shares_outstanding": ratio_series(
                "shares_outstanding", [1_000_000.0, 2_000_000.0]
            ),
        }
    )
    fig, ax = plt.subplots()

    MarketCapChart().render(ax, fundamentals)

    assert len(ax.lines) == 1
    # $10 * 1,000,000 shares, $20 * 2,000,000 shares
    assert list(ax.lines[0].get_ydata()) == [10_000_000.0, 40_000_000.0]
    plt.close(fig)


def test_falls_back_to_no_data_when_shares_outstanding_unavailable():
    fundamentals = fundamentals_with(
        {
            "price": money_series("price", [10.0]),
            "shares_outstanding": unavailable_series("shares_outstanding"),
        }
    )
    fig, ax = plt.subplots()

    MarketCapChart().render(ax, fundamentals)

    texts = [t.get_text() for t in ax.texts]
    assert "No Data" in texts
    plt.close(fig)
