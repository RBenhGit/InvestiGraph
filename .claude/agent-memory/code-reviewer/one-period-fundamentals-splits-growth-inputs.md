---
name: one-period-fundamentals-splits-growth-inputs
description: The growth-rate fallback chain only works on an ANNUAL CompanyFundamentals while TTM-EPS growth only works on a QUARTERLY one — the original TS fetched both statements in one call, the port cannot
metadata:
  type: project
---

`valuation/growth.py`'s `historical_1y/3y_growth_percent` return `None` unless
`fundamentals.period == Period.ANNUAL`; `calculate_ttm_eps_growth_percent` returns `None` unless it
is `Period.QUARTERLY`. `CompanyFundamentals` carries exactly one period, so no single fetch feeds
both.

**Why:** the Eps_Evaluation original (`legacy/eps_evaluation/src/data/twelvedata/index.ts`) fetched
the quarterly *and* annual income statements in one `Promise.all` and built one `StockData` holding
both; Financial_Charts' canonical template is single-period. The port is faithful function by
function, but the composition the original relied on no longer exists. With
`analyst_estimate_5y_percent` permanently `None` in this merge, a quarterly fetch collapses the
whole chain to `MISSING_GROWTH_RATE`.

**How to apply:** on any diff that wires valuation into the web/CLI layer, check which `period` the
fundamentals came from. Charts default to `annual` (`config.DEFAULT_PERIOD`) but the picker exposes
`quarterly`/`ttm`; if the valuation panel reuses the request's period, fair values silently vanish
for every ticker on those settings while the charts still render.
