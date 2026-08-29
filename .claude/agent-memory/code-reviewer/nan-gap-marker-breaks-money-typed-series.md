---
name: nan-gap-marker-breaks-money-typed-series
description: Emitting a bare float("nan") as a gap marker into a Money-valued MetricSeries produces a mixed-type series; every Money renderer does p.value.value / p.value.as_base_units() and crashes with AttributeError. Found 2026-08-29 in ttm_series(mark_gaps=True).
metadata:
  type: project
---

`Point.value` is typed `Money | float`, and `MetricSeries._consistent_money_tagging` only checks
consistency *among the Money points* — it does not reject a series that mixes `Money` and bare
`float`. So appending `Point(date=d, value=float("nan"))` into an otherwise-`Money` series
validates cleanly and the bug surfaces only at the render boundary.

**Why:** the NaN-gap-marker convention (see [[skipped-points-interpolate-across-gaps]]) was
designed for *dimensionless float* series (`resolve_trailing`'s ratios, `derived.resolve`'s
margins), where NaN is the same type as a real value. `ttm_series` is different: it sums flow
metrics that are `Money` (revenue, net_income, eps, fcf, ebitda, R&D, SG&A, dividends_paid, ebit).
A bare-float NaN in those series is a *type* violation, not just a value marker.

Every Money consumer dereferences the wrapper unconditionally:
- `charts/base.py`'s `render_money_bar` -> `p.value.value`
- `charts/base.py`'s `render_money_line` -> `p.value.as_base_units()`
- `web/chart_data.py`'s `_money_bar` (`p.value.value`) and `_money_line` / `_market_cap`
  (`p.value.as_base_units()`)
- `charts/builtins/price.py`, `charts/builtins/valuation.py`, `market_cap.py`

Reproduced 2026-08-29: `derive_ttm_fundamentals()` on a quarterly `revenue` series with a
missing-quarter gap, then `build_chart_specs(ttm, "fundamentals")` ->
`AttributeError: 'float' object has no attribute 'value'`. Same for the matplotlib path.

**How to apply:** when reviewing any change that introduces a sentinel/marker point into a
`MetricSeries`, first check whether that series can be `Money`-typed. If it can, the marker must be
`Money(value=float("nan"), currency=..., scale=...)` matching the series' own tagging, not a bare
float — or the renderers must learn to unwrap defensively. Also note that `pytest` passing is not
evidence here: the gap tests assert on `math.isnan(point.value)`, which is true for a bare float
*and* would be false for a `Money`, so they inadvertently lock in the broken shape. No test in the
suite feeds a derived-TTM `CompanyFundamentals` with a gap into any renderer.

Related: [[skipped-points-interpolate-across-gaps]], [[derived-metric-no-data-gating-gap]].
