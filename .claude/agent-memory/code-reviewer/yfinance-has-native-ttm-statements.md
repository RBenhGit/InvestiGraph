---
name: yfinance-has-native-ttm-statements
description: yfinance DOES expose native TTM statements (ttm_income_stmt / ttm_cashflow / ttm_financials) — verified live on 1.5.1; any doc claiming "no source's API returns a true TTM statement" is false
metadata:
  type: reference
---

`yfinance.Ticker` exposes `ttm_income_stmt` / `ttm_incomestmt` / `ttm_financials` /
`ttm_cash_flow` / `ttm_cashflow`. Verified live 2026-08-28 against the pinned version
(yfinance 1.5.1): `yf.Ticker('AAPL').ttm_income_stmt` returned a 33-row x 1-column DataFrame
dated 2026-06-30 with `Total Revenue = 4.66823e11`. There is no TTM balance sheet (the concept
doesn't apply to a snapshot). Twelve Data's statement endpoints take `period=annual|quarterly`
only — no TTM.

**Why it matters:** InvestiGraph derives TTM itself by summing four quarters
(`template/trailing.py`'s `derive_ttm_fundamentals`, added 2026-08-28). That is a deliberate,
uniform-across-sources design choice — but the README justifies it with "neither source's API
returns a true TTM statement", which is checkably wrong for yfinance. A derived 4-quarter sum can
also legitimately disagree with Yahoo's own published TTM (restatements, adjustments), so "our
TTM ≠ Yahoo's TTM" is expected, not a bug.

**How to apply:** treat any claim in README/`docs/SPEC.md` about what an upstream API can or can't
supply as a claim to verify (import the library, check the attribute) rather than accept. Don't
recommend switching to yfinance's native TTM without noting it covers income statement + cash flow
only, so a hybrid would still need the derived path for everything else.
