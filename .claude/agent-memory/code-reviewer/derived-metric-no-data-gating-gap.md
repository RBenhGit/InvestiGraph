---
name: derived-metric-no-data-gating-gap
description: render_or_no_data gates only on raw input-metric availability, not on whether a DerivedMetric's resolve() actually produced overlapping points — derived-metric charts can render blank instead of "No Data"
metadata:
  type: project
---

`src/financial_charts/charts/base.py`'s `render_or_no_data()` decides whether to show the
"No Data" card by checking `fundamentals.series[metric_id].available` for each id in
`chart.required_metrics`. For a chart built on `template/derived.py`'s `resolve()`
(e.g. `FCFMarginChart`, whose `required_metrics` lists the *input* metrics like
`free_cash_flow`/`revenue`, not the derived id), that gate has no visibility into whether
`resolve()`'s date-intersection actually produced any points. If both inputs are marked
`available=True` individually but share zero common dates (plausible with yfinance: `revenue`
comes from `financials`, `free_cash_flow` from a separate `cashflow` DataFrame, each filtered
for NaN independently — see CLAUDE.md's "sparse/None fields" gotcha), `resolve()` correctly
sets its own `MetricSeries.available=False`, but nothing surfaces that back to
`render_or_no_data`. The chart's `render()` then plots empty x/y arrays — a blank card, not the
required "No Data" text.

Confirmed 2026-07-19/20 while reviewing the "derived quantities" feature
(`template/derived.py`, `charts/builtins/fcf_margin.py`, `charts/catalog.py`). The shipped test
`fcf_margin_test.py::test_renders_nothing_when_dates_do_not_overlap` documents this exact
scenario but only asserts "does not crash" — it does not assert the "No Data" fallback
appears, so the gap shipped un-flagged by the test suite.

**Why:** CLAUDE.md explicitly requires "every chart can degrade to 'No Data' gracefully" for
missing/misaligned data — a blank chart with no explanation violates that, even though it
doesn't crash.

**How to apply:** for any future chart built on a `DerivedMetric`/`resolve()` (not just
`FCFMarginChart`), check whether the chart's own `render()` inspects the resolved series'
`available` flag before plotting, or whether the shared gating mechanism has been extended to
account for it. If neither, flag as Critical — same failure shape as this one.

**Update 2026-07-25:** confirmed fixed going forward, not just for `FCFMarginChart`. Reviewing
Task 16 (`3644bb1..06bf179`, chart inventory expansion), every new chart built on a
`DerivedMetric` — `RatiosChart`/`current_ratio`, `DebtLeverageChart`/`debt_to_equity`,
`ReturnOnCapitalChart`/ROCE+ROIC, `ValuationChart`/`book_value_per_share` — explicitly checks
`resolve(...).available` in its own `render()` before plotting, and each has a test that asserts
the "No Data" text actually appears for a shared-no-common-date scenario (not just "doesn't
crash", the gap that let the original issue ship un-flagged). Treat this as the established,
correctly-followed convention now — only flag if a *new* derived-metric chart skips it.
