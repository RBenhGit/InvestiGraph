from pathlib import Path

import matplotlib.pyplot as plt
from jinja2 import BaseLoader, Environment

from financial_charts.dashboard.layout import render_chart_cards, render_grid_figure
from financial_charts.template.models import CompanyFundamentals

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
    fundamentals: CompanyFundamentals, chart_set_name: str = "fundamentals"
) -> str:
    cards = render_chart_cards(fundamentals, chart_set_name)
    return _TEMPLATE.render(
        ticker=fundamentals.ticker,
        market=fundamentals.market.value,
        currency=fundamentals.currency.value,
        cards=cards,
        source_limits=fundamentals.source_limits,
    )


def write_output(
    fundamentals: CompanyFundamentals, out: Path, chart_set_name: str = "fundamentals"
) -> None:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    suffix = out.suffix.lower()

    if suffix == ".html":
        out.write_text(render_html(fundamentals, chart_set_name))
    elif suffix in {".png", ".pdf"}:
        fig = render_grid_figure(fundamentals, chart_set_name)
        fig.savefig(out)
        plt.close(fig)
    else:
        raise ValueError(
            f"unsupported output format: {suffix!r} (expected .html, .png, or .pdf)"
        )
