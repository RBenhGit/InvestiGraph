from pathlib import Path

import matplotlib.pyplot as plt
from jinja2 import BaseLoader, Environment

from investigraph.dashboard.layout import render_chart_cards, render_grid_figure
from investigraph.template.models import CompanyFundamentals, Period

_PAGE_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{{ ticker }} — Fundamentals</title>
<style>
  body { font-family: sans-serif; margin: 2rem; }
  .grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 1.5rem; }
  .card { border: 1px solid #ddd; border-radius: 8px; padding: 1rem; }
  .card img { width: 100%; }
  .limits { margin-top: 1.5rem; color: #a33; }
</style>
</head>
<body>
<h1>{{ ticker }} ({{ market }}) — {{ currency }}</h1>
<div class="grid">
{% for card in cards %}
  <div class="card">
    <h3>{{ card.title }}</h3>
    <img src="data:image/png;base64,{{ card.png_base64 }}" alt="{{ card.title }}">
  </div>
{% endfor %}
</div>
{% if source_limits %}
<div class="limits">
  <h3>Source limits</h3>
  <ul>
  {% for limit in source_limits %}<li>{{ limit }}</li>{% endfor %}
  </ul>
</div>
{% endif %}
</body>
</html>
"""

_ENV = Environment(loader=BaseLoader(), autoescape=True)
_TEMPLATE = _ENV.from_string(_PAGE_TEMPLATE)


def render_html(
    fundamentals_by_period_range: dict[tuple[Period, str], CompanyFundamentals],
    chart_set_name: str = "fundamentals",
) -> str:
    """`fundamentals_by_period_range` is the grouped-fetch result from
    `web.service.load_fundamentals_for_charts` — every entry shares the same
    ticker/market/currency (only period/range differ), so any one of them
    supplies those page-level fields; `source_limits` is merged across all of
    them so a limit surfaced under one (period, range) pair isn't lost.
    """
    cards = render_chart_cards(fundamentals_by_period_range, chart_set_name)
    any_fundamentals = next(iter(fundamentals_by_period_range.values()))
    source_limits = []
    for fundamentals in fundamentals_by_period_range.values():
        source_limits.extend(
            limit for limit in fundamentals.source_limits if limit not in source_limits
        )
    return _TEMPLATE.render(
        ticker=any_fundamentals.ticker,
        market=any_fundamentals.market.value,
        currency=any_fundamentals.currency.value,
        cards=cards,
        source_limits=source_limits,
    )


def write_output(
    fundamentals_by_period_range: dict[tuple[Period, str], CompanyFundamentals],
    out: Path,
    chart_set_name: str = "fundamentals",
) -> None:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    suffix = out.suffix.lower()

    if suffix == ".html":
        out.write_text(render_html(fundamentals_by_period_range, chart_set_name))
    elif suffix in {".png", ".pdf"}:
        any_fundamentals = next(iter(fundamentals_by_period_range.values()))
        fig = render_grid_figure(
            fundamentals_by_period_range, any_fundamentals.ticker, chart_set_name
        )
        fig.savefig(out)
        plt.close(fig)
    else:
        raise ValueError(
            f"unsupported output format: {suffix!r} (expected .html, .png, or .pdf)"
        )
