---
name: skipped-points-interpolate-across-gaps
description: derived.resolve/resolve_trailing degrade a bad point by dropping it from the list, and both renderers (matplotlib ax.plot, Plotly mode:'lines') then connect straight across the hole — a dropped run reads as real interpolated data
metadata:
  type: project
---

Both computation entry points in `template/` — `derived.resolve()` and `trailing.resolve_trailing()`
— implement "degrade one point, not the whole series": a `compute` that raises
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
a zero-equity guard is rare, a negative-EPS guard is not. Related: [[derived-metric-no-data-gating-gap]].
