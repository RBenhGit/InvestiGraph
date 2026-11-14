---
name: nan-poisons-whole-series-aggregate
description: The NaN gap-marker convention means any whole-series aggregate (trend fit, CAGR, mean, sum) computed over a TTM/derived series silently becomes all-NaN — and Pydantic's model_dump_json launders those to JSON null, which the frontend then dereferences
metadata:
  type: project
---

This repo deliberately emits NaN *points* into a series to break a chart line at a gap
(see [[skipped-points-interpolate-across-gaps]] and
[[nan-gap-marker-breaks-money-typed-series]]). That convention is safe for renderers, which
plot point-by-point — but it is **not** safe for any function that reduces the whole series
to one number or fits a curve across all points. One NaN propagates through every sum/mean,
so the aggregate becomes NaN and *every* fitted value becomes NaN, not just the gap index.

Found 2026-09-10 reviewing `feat/per-chart-config`: `charts/fit.py`'s `fit_linear`/
`fit_exponential` guard only for `len < 2`, identical dates, and (exponential only)
non-positive values — `math.log(nan)` is `nan`, not an exception, and `any(v <= 0 ...)` is
`False` for NaN, so both guards pass. Reproduced with a quarterly EPS series missing one
quarter: `derive_ttm_fundamentals` (which calls `ttm_series(..., mark_gaps=True)` for every
flow metric) produced 3 NaN points out of 8, and the fit came back
`fitted_values=[nan]*8, rate=nan`. This is directly reachable because EPS and FreeCashFlow
now declare `Period.TTM`, so their web series *routinely* carries gap markers.

**Why it isn't caught by tests:** `fit_test.py` only feeds hand-built clean series. The
NaN path never reaches the fit in any test.

**The second half of the bug — NaN becomes `null`, not `NaN`:** `app.py` serializes with
Pydantic's `model_dump_json()` specifically to launder NaN into valid JSON, which emits
`null`. So the frontend receives `fit: {linear_rate_per_year: null, ...}` — a *non-null
object with null fields*. A guard like `if (!series.fit) return null;` does not catch this.
In `index.html`'s `fitTrace`, `rate.toFixed(2)` then throws
`TypeError: Cannot read properties of null`, while the exponential branch `(rate * 100).toFixed(1)`
does something worse: `null * 100 === 0`, so it silently renders a fabricated "0.0%/yr" label.

**How to apply:** whenever a diff adds a function that consumes a whole `MetricSeries`
(fit, CAGR, mean, total, correlation), check whether that series can carry gap markers —
any flow metric under `Period.TTM`, or anything out of `derived.resolve`/`resolve_trailing`.
If it can, the function must filter non-finite points before computing (and decide whether a
partial fit is meaningful) rather than assuming finite input. Then check the JSON boundary:
NaN-safe on the Python side is not NaN-safe on the JS side, because the laundering turns it
into `null`, and `null` arithmetic coerces to `0` instead of throwing.

Related: [[nan-gap-marker-breaks-money-typed-series]], [[skipped-points-interpolate-across-gaps]].
