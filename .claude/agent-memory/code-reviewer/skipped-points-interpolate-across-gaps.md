---
name: skipped-points-interpolate-across-gaps
description: template/ computations degrade a bad point by dropping it from the list, and the renderers then connect straight across the hole — a dropped run reads as real interpolated data. All three computation paths (resolve_trailing, derived.resolve, ttm_series) now mark gaps as NaN instead of dropping them. FIXED as of 2026-08-29; watch for the Money-vs-float typing trap this hit on the first attempt (see below) when reviewing similar NaN-marker code elsewhere.
metadata:
  type: project
---

**Status (fixed 2026-08-29):** All three computation paths now mark a failed/gapped point as
`float('nan')` instead of omitting it:
- `trailing.resolve_trailing()` — fixed earlier (2026-08-28).
- `derived.resolve()` — its `except` block now appends `Point(date=d, value=float("nan"))` instead
  of `continue`; collapses to `available=False` only if every point is NaN. Shared `_is_real()`
  helper lives in `derived.py` and is imported by `trailing.py` (no duplicate).
- `trailing.ttm_series()` gained a `mark_gaps: bool = False` keyword. Default (`False`) preserves
  the original skip-the-gap behavior, because `valuation/growth.py`
  (`calculate_ttm_eps_growth_percent`) and `valuation/resolve_eps.py` (`_template_ttm_eps`) both
  depend on gapped windows being *absent*, not NaN-valued — they search by date among present
  points (`_find_year_ago_point`) or take `max(points, key=date)` expecting the latest point to be
  real. `derive_ttm_fundamentals()` (the chart-rendering path) is the only caller that now passes
  `mark_gaps=True`, so its flow-metric series and the `net_margin` it recomputes via
  `derived.resolve()` both correctly break the line at a missing-quarter gap.

**Follow-up bug found and fixed same day (2026-08-29, deep integration audit):** the first version
of `ttm_series(mark_gaps=True)` emitted a bare `Point(date=..., value=float("nan"))` for every
flow metric — but flow metrics (revenue, net_income, eps, fcf, ebitda, R&D, SG&A, dividends_paid,
ebit) are `Money`-valued, not float. A bare float mixed into an otherwise-`Money` series passed
`MetricSeries`'s validation (`_consistent_money_tagging` only checks consistency *among* the
`Money` points) and then crashed every renderer that assumes `.value` is `Money` uniformly:
`render_money_bar` (`p.value.value`), `render_money_line` (`p.value.as_base_units()`), and
`web/chart_data.py`. Concretely, this turned "any ticker with one missing quarterly statement
cell, viewed at `--period ttm`" from a silently-wrong chart into a hard 500 on the whole dashboard
— worse than the bug this fix was meant to close. Fixed by a new `_nan_like(value)` helper in
`trailing.py` that returns `Money(value=float("nan"), currency=value.currency, scale=value.scale)`
when `value` is `Money`, a bare float otherwise; both `ttm_series` gap-emission sites now call it
instead of constructing `float("nan")` directly. `derived.resolve()`'s own marker was never
affected — every `DerivedMetric.compute` in `derived.py` (`ratio`, `_roce`, `_roic`,
`_book_value_per_share`) returns a plain `float`, so its NaN marker was correctly typed from the
start; the bug was specific to `ttm_series`, the one path applying the convention to a
`Money`-valued series.

Regression tests: `derived_test.py`'s three `test_resolve_*` tests were updated to assert NaN
instead of a shortened list; `trailing_test.py` gained
`test_ttm_series_mark_gaps_emits_nan_instead_of_skipping` (now asserts a `Money`-typed NaN, not a
bare float), `test_derive_ttm_fundamentals_marks_flow_metric_gap_as_nan` (same),
`test_derive_ttm_fundamentals_net_margin_breaks_at_a_flow_metric_gap`, and a new
`test_derive_ttm_fundamentals_gap_point_renders_without_crashing` that feeds a gapped
`derive_ttm_fundamentals` output into the real `render_money_bar` — the producer→renderer seam the
earlier tests didn't cover, and the one that would have caught this bug before it shipped.

The original finding: computations in `template/` implement "degrade one point, not the whole
series": a `compute` that raises
`ZeroDivisionError/ValueError/AttributeError/TypeError` is caught and the point is **omitted from
`MetricSeries.points`**. Every chart then does `dates = [p.date for p in series.points]` /
`values = [p.value for p in series.points]` and hands the two parallel lists to `ax.plot`
(matplotlib) or a Plotly `{type:'scatter', mode:'lines'}` trace. Neither renderer knows a point was
dropped — both just connect element *i* to element *i+1*, so a dropped run renders as one straight
segment spanning the hole, at plausible-looking interpolated y-values.

Reproduced 2026-08-12 on `charts/builtins/pe_ratio.py` (P/E TTM, daily price driver): a company
with a negative trailing EPS for one fiscal year has all ~365 daily points in that year skipped by
`trailing._pe`'s non-positive-EPS guard, and the chart draws a single 366-day segment from P/E 20.0
to P/E 25.0 across the loss year. Identical output on the web path.

**Why:** this is an *investor-evaluation* tool. Omitting a point is the right degradation for the
data model, but at the display boundary "undefined" and "smoothly interpolated" look identical to
the reader, and the interpolated region is fabricated. The wider the input cadence gap (a daily
driver joined to annual statements), the longer the fabricated segment.

**How to apply:** whenever reviewing a chart that plots a computed series whose points can be
*individually* skipped (anything resolved via `resolve`/`resolve_trailing` with a guard in its
`compute`), check whether the gap survives to the renderer. The cheap fix is to emit `float('nan')`
for skipped points instead of omitting them — matplotlib breaks the line at NaN, and
`chart_data.py` already launders NaN to JSON `null` via Pydantic (Plotly breaks the line at
`null`), a path the price SMA warm-up already relies on. Risk scales with how common the guard is:
a zero-equity guard is rare, a negative-EPS guard is not.

Blast radius grew on 2026-08-28: `trailing.derive_ttm_fundamentals()` runs **every** flow metric
(revenue, net_income, eps, fcf, ebitda, R&D, SG&A, dividends_paid, ebit) through `ttm_series` for
`--period ttm` / `?period=ttm`, so the 330-day skip now affects the whole dashboard under that
period, not just the three trailing metrics. Bar charts (revenue/net income/EPS/FCF) show an honest
missing bar; the line charts (e.g. `charts/builtins/expenses.py`'s R&D vs SG&A) are the ones that
would interpolate across a skipped window.
Related: [[derived-metric-no-data-gating-gap]].
