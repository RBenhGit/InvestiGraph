---
name: yahoo-trailing-eps-tase-currency
description: Yahoo info['trailingEps'] for USD-filing TASE tickers is in ILS shekels (quote currency), not USD or agorot — verified live 2026-11-13
metadata:
  type: reference
---

Yahoo's `info['trailingEps']` for TASE tickers that file in USD (`financialCurrency` USD,
`currency` ILA) is denominated in **ILS shekels**, while `currentPrice` is in agorot.
Verified 2026-11-13: QLTU.TA 15.36 (template 4.676 USD x 3.2 = 14.96), ESLT.TA 42.32
(ttm diluted 13.29 USD x 3.2 = 42.5), NICE.TA, TEVA.TA all consistent with trailingPE =
(price/100)/trailingEps.

**Why:** `resolve_eps`'s 5% Yahoo-divergence check compares against the FX-converted
template EPS (fix/tase-usd-eps-fx); that is only correct because Yahoo is in quote currency.
Nothing in code asserts this — Yahoo exposes no currency for trailingEps.

**How to apply:** If a review touches the divergence check or the yahoo-fallback branch for
mismatched-currency tickers, re-verify live rather than trusting this; if Yahoo ever switched
to financialCurrency, yahoo-fallback would swap in a USD figure labeled ILS (~3.2x too low).
Related: [[valuation-chain-drops-money-currency-tag]].
