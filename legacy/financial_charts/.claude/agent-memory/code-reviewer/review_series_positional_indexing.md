---
name: review-series-positional-indexing
description: Recurring InvestiGraph defect class — positional indexing into a metric series used as a proxy for calendar distance, which breaks because series builders silently drop points
metadata:
  type: project
---

When reviewing anything that indexes into a `MetricSeries` by position (`points[-5]`,
`values[3]`, "N years ago") to mean "N periods earlier in time", verify the code also
checks the *dates*. In this codebase positional offset is NOT a reliable proxy for
calendar offset.

**Why:** the series builders deliberately drop points. `sources/yfinance/adapter.py`'s
`_statement_series` filters `pd.notna(val)`; `sources/twelvedata/adapter.py`'s
`_income_series` skips rows whose field is `None`; `template/trailing.py`'s `ttm_series`
skips any 4-quarter window spanning more than `_MAX_QUARTER_WINDOW_DAYS` (330). So a
company with one missing quarter yields a series where index `-5` can be two years back
rather than one. Caught in Phase 5 review (since fixed): `valuation/growth.py`'s
`calculate_ttm_eps_growth_percent` guarded only on `len(...)` and reported 200% growth
where the true one-year figure was 33%. A `len(points) >= N` check does not establish
that the points are *consecutive* — that is the specific gap to look for.

**How to apply:** on any diff touching `valuation/` or `template/trailing.py`, reproduce
with a series that has an interior missing quarter before accepting a count-based guard.
Also check any user-facing "as of {date}" provenance string: the date must come from the
point actually used, not the latest raw point in the source series — the same root cause
produced a second, separate defect in that same phase.
