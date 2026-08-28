---
name: valuation-chain-drops-money-currency-tag
description: The ported valuation chain (resolve_eps -> lynch/rule_one -> SavedValuation) carries bare floats with no currency, so a statement-currency EPS can be compared against a market-currency price
metadata:
  type: project
---

New instance (found 2026-08-28 at the Phase 4-6 convergence gate) of the defect class in
[[money-currency-guard-bypassed-via-raw-division]].

`valuation/resolve_eps.py` unwraps the template's `eps` `Money` via `as_base_units()` and returns a
bare `float`; `valuation/lynch|rule_one` return a bare `fair_value` float; `history/SavedValuation`
has one `currency` field for both `current_price` and `eps_ttm`/fair values. Nothing carries a
currency tag through, and `resolve_eps`'s `detail` string hardcodes `$`.

**Why:** the `eps` series is tagged with the *income statement's* currency (Twelve Data
`income_statement` `meta.currency`), while `CompanyFundamentals.currency` and the `price` series are
the *market's* currency (`display_currency`; TASE agorot are divided by 100 into ILS). Those two are
independently sourced and genuinely differ for dual-listed companies (Teva files USD, trades ILS) —
which is the exact case `Money` exists to make loud.

**How to apply:** when reviewing anything that wires a fair value against a price (Phase 7's panel,
the CLI's `valuate`, saved-valuation upside %), check that the two sides are known to share a
currency — the guard cannot come from `Money` any more, because it was dropped at `resolve_eps`.
Either re-tag or restrict the feature to `Market.US` explicitly.
