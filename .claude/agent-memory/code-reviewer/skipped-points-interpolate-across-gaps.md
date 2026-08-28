---
name: skipped-points-interpolate-across-gaps
description: template/ computations degrade a bad point by dropping it from the list, and the renderers then connect straight across the hole — a dropped run reads as real interpolated data. resolve_trailing is FIXED (NaN); derived.resolve and ttm_series still drop.
metadata:
  type: project
---

**Status (re-checked 2026-08-28):** `trailing.resolve_trailing()` now appends `float('nan')` for a
failed point instead of omitting it — that half is fixed. Still dropping silently:
`derived.resolve()` (its `except` block `continue`s) and `trailing.ttm_series()` (a window whose
span exceeds `_MAX_QUARTER_WINDOW_DAYS = 330`, i.e. a missing quarter, is `continue`d). The web
renderer is `mode: 'lines+markers'` unless a spec sets `markers: false` (daily-density series), so
a single surviving point is at least visible — but a *gap* still reads as an interpolated segment.

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
