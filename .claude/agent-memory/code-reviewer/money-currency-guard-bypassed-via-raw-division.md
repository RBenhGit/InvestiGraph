---
name: money-currency-guard-bypassed-via-raw-division
description: charts that manually call two different Money series' .as_base_units() and divide them bypass Money.require_same_currency, unlike charts that route the same combination through derived.ratio()
metadata:
  type: project
---

Found 2026-07-25 reviewing commit `3644bb1..06bf179` (Task 16, chart inventory expansion,
`feature/source-commissioning`). `template/derived.py`'s `ratio()` exists specifically to combine
two `Money` values safely: it calls `numerator.require_same_currency(denominator)` before
dividing `as_base_units()`, so a currency mismatch raises `ValueError` (caught upstream, chart
degrades to "No Data") instead of silently producing a wrong number. `PERatioChart`
(`charts/builtins/pe_ratio.py`) and `ReturnOnEquityChart`
(`charts/builtins/return_on_equity.py`) both correctly route their two-`Money` combination through
`ratio()` — `pe_ratio.py`'s own comment even names "a currency mismatch between the price and
financial statement currencies" as the reason for its `except ValueError`.

**STATUS (re-verified 2026-08-12): both original instances are now guarded.** The dividend-yield
math moved to `template/trailing.py`'s `_dividend_yield`, which calls
`price.require_same_currency(dividends_ttm)` before hand-dividing; `ValuationChart.render()`
compares `price_points[0].value.currency != equity_points[0].value.currency` up front and draws
"No Data" on mismatch. Keep the **How to apply** rule below — the *class* of bug is still live for
any new chart — but don't re-report these two.

Historical detail: `DividendYieldChart.render()` (`charts/builtins/dividend_yield.py`) and
`ValuationChart`'s module-level `_nearest_price()` helper (`charts/builtins/valuation.py`) called
`.as_base_units()` on each `Money` operand by hand and divided the raw floats — `price` vs.
`dividends_paid`, and `price` vs. `total_equity`-derived book value per share, respectively.
Neither called `require_same_currency`, so if a ticker's price-quote currency and
financial-statement currency genuinely differ (real in both adapters: yfinance's
`info["currency"]` vs. `info["financialCurrency"]`; Twelve Data's `time_series` endpoint's own
`meta.currency` vs. the `income_statement` endpoint's own `meta.currency` — two independently
sourced fields, not guaranteed to agree), these two charts silently compute a nonsensical
yield/P-B ratio instead of degrading to "No Data" the way `PERatioChart` does for the identical
risk. `MarketCapChart` looks similar (`price.as_base_units() * shares`) but is actually safe —
`shares` there is a plain float (`shares_outstanding`), not a second `Money`, so there's no second
currency to mismatch.

**Why:** `Money`/`require_same_currency` exists precisely to make the TASE agorot-vs-shekels
class of bug loud instead of silent (CLAUDE.md's core "Money" invariant). A chart that manually
unwraps two `Money` values and divides raw numbers defeats that guard even when each individual
value is perfectly valid.

**How to apply:** when reviewing any new chart (or derived metric) that combines two *different*
metric series where at least two of them are `Money`-typed, check whether the combination goes
through `derived.ratio()` (or an equivalent explicit `require_same_currency` call) rather than
directly calling `.as_base_units()`/`.value` on each side and dividing/multiplying the raw
numbers. Flag as Critical if not — same failure shape as this one, and it produces a
plausible-looking wrong number rather than a crash or a "No Data" card, which is worse for a
tool whose stated purpose is investor evaluation.
