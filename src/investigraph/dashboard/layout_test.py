import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from financial_charts.charts.builtins._test_helpers import (
    fundamentals_with,
    money_series,
)
from financial_charts.dashboard.layout import render_chart_cards, render_grid_figure


def _fundamentals():
    return fundamentals_with({"price": money_series("price", [1.0, 2.0, 3.0])})


def test_render_chart_cards_returns_one_card_per_chart_in_the_set():
    cards = render_chart_cards(_fundamentals(), "fundamentals")

    assert len(cards) == 6
    titles = [c.title for c in cards]
    assert "Price" in titles
    assert "Margins" in titles
    for card in cards:
        assert card.png_base64  # non-empty base64 payload


def test_render_grid_figure_has_an_axes_per_chart():
    fig = render_grid_figure(_fundamentals(), "fundamentals")

    assert len(fig.axes) >= 6
    plt.close(fig)


def test_render_grid_figure_titles_include_ticker():
    fig = render_grid_figure(_fundamentals(), "fundamentals")

    assert "TEST" in fig._suptitle.get_text()
    plt.close(fig)
