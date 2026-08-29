---
name: nth-of-type-vs-class-column-highlight
description: style.css highlights history/valuation table columns with `td.table-val:nth-of-type(N)`, which counts ALL td siblings not just .table-val ones — and index.html's rowspan rows shift every index
metadata:
  type: project
---

`src/investigraph/web/static/style.css` highlights a valuation column with
`.history-table td.table-val:nth-of-type(4)`. `:nth-of-type` counts among **all** `td`
siblings by element type — the `.table-val` class is only an extra filter on the matched
element, it does not restrict the counting set.

Two live consequences in this repo:

1. **index.html history table** (`renderHistoryTable` in `app.js`): Date/Evaluator/Price
   cells are emitted only on the first row of a rowspan group. So a base row has tds
   Date(1) Ticker(2) Eval(3) Price(4) RuleOne(5)…, while a bear/bull continuation row has
   Ticker(1) RuleOne(2) Growth(3)…. **No single index can target Rule #1 in both.** As of
   the 2026-08 Lynch removal `nth-of-type(4)` matches nothing on base rows and the
   *Assumptions* cell (not `.table-val`, so still nothing) on continuation rows — i.e. the
   highlight is silently dead. This predates the Lynch removal.
2. **valuations.html** (`valuations.js`): flat rows, no rowspan, so `nth-of-type(4)` does
   correctly land on Rule #1 Base FV after the Lynch columns were dropped.

**Why:** column-count changes silently re-point these selectors; nothing tests computed
styles, so a broken highlight is invisible to both suites.

**How to apply:** whenever a `<td>`/`<th>` is added to or removed from either table, hand-
check every `nth-of-type` in style.css against *both* the first-row and continuation-row td
sequences. Prefer suggesting an explicit class (e.g. `.table-val-primary`) over an index.
Related: [[review_series_positional_indexing]] — same "positional index silently drifts"
failure mode, different medium.
