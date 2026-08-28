"""EPS resolution: reconciles the template's own TTM EPS against Yahoo's
independent `trailing_eps` when the two diverge, porting Eps_Evaluation's
`resolveEpsWithFallback` (legacy/eps_evaluation/src/data/resolveEps.ts) onto
Financial_Charts' canonical `CompanyFundamentals` template instead of Twelve
Data's raw `StockData` shape.

The original flagged a stale Twelve Data `epsTtm` by comparing a *locally
computed* trailing P/E against Twelve Data's own `statistics.trailing_pe` — an
endpoint this merge drops (`statistics` was reference-only, see
`docs/MERGE_SPEC.md`). Rebuilt here to compare the template's own TTM EPS
(via `template/trailing.py`'s `ttm_series`) directly against Yahoo's
`trailing_eps`, at the same >5% divergence threshold the original used.

One structural consequence of dropping the second Twelve Data endpoint: staleness
can now only be *detected* when Yahoo's `trailing_eps` is itself available and
usable for comparison — there's no longer an independent Twelve-Data-only signal
to flag it. `'twelvedata-stale-no-fallback'` is preserved as a real, reachable
label (not just kept for API-shape continuity): it fires when Yahoo's own figure
is present but not > 0 (e.g. a loss-making trailing year — matching the original's
`yahooEps > 0` guard on whether a figure is trustworthy enough to *show*, which is
a stricter bar than whether it's usable to *detect* divergence with).

**Currency guard (found in the convergence review before Phase 7):** `eps`'s `Money`
is tagged with the income statement's currency (`financial_currency`), which is not
always `fundamentals.currency` (the market/price currency, `display_currency`) — a
dual-listed company can legitimately report financials in a different currency than
the one its shares trade in (see `template/models.py`'s `CompanyFundamentals`
docstring; concretely, `sources/twelvedata/adapter.py` can produce a USD `eps` series
for a TASE ticker whose `price` series and `fundamentals.currency` are ILS). Silently
unwrapping the `Money` with `as_base_units()` — which only rescales *unit* (ones vs.
millions), not currency — would combine a USD EPS with an ILS price into a nonsense
fair value/upside%, exactly the class of bug `Money.require_same_currency` exists to
prevent everywhere else `Money` is combined. This module has no FX conversion (an
architectural constraint, not an oversight — see `docs/MERGE_SPEC.md`), so there is no
"convert and proceed" option: a currency mismatch here must refuse to resolve, the
same way a missing TTM EPS does.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from investigraph.sources.yahoo_consensus.models import AnalystConsensus
from investigraph.template.models import CompanyFundamentals, Currency, Money, Point
from investigraph.template.trailing import ttm_series

# Same threshold as the original `detectStaleTtmEps` (calibrated live: two healthy
# tickers showed 0.04%-1.5% divergence, a confirmed-stale one showed 7.3%).
_STALE_DIVERGENCE_THRESHOLD = 0.05

EpsSource = Literal["twelvedata", "yahoo-fallback", "twelvedata-stale-no-fallback"]


@dataclass(frozen=True)
class ResolvedEps:
    eps_ttm: float
    # The currency `eps_ttm` is actually in — always `fundamentals.currency` by
    # construction (see the module docstring's currency guard): a template EPS
    # in a different currency never reaches this point, and Yahoo's `trailing_eps`
    # (no currency of its own in `AnalystConsensus`) is used only as a same-
    # currency replacement, carrying forward the same assumption the original
    # TS made implicitly. A future caller combining `eps_ttm` with a price must
    # still confirm this against that price's own currency rather than assume
    # it — this field exists so that check has something to check against.
    currency: Currency
    source: EpsSource
    # Human-readable note on the concrete date/source of whichever figure was
    # used — never invented, always derived from the actual data present. The
    # UI must never show a Yahoo-sourced number as if it came from Twelve Data.
    detail: str


def resolve_eps(
    fundamentals: CompanyFundamentals, consensus: AnalystConsensus | None
) -> ResolvedEps | None:
    """Resolve the EPS actually shown to the user.

    A healthy template TTM EPS is used as-is. When Yahoo's independently-sourced
    `trailing_eps` is available and diverges from it by more than 5%, Yahoo's
    figure replaces it — unless Yahoo's own figure isn't itself usable (not
    positive), in which case the template's figure is kept but labeled as
    flagged. Returns `None` when the template has no usable TTM EPS to resolve
    from, or when it has one but its currency doesn't match `fundamentals.currency`
    (see the module docstring's currency guard) — both are precondition failures,
    not staleness questions.
    """
    template_point = _template_ttm_eps(fundamentals)
    if template_point is None:
        return None
    template_money = template_point.value
    if not isinstance(template_money, Money):
        return None
    if template_money.currency != fundamentals.currency:
        return None
    template_eps = template_money.as_base_units()
    latest_date = template_point.date
    currency = fundamentals.currency
    symbol = _currency_symbol(currency)

    yahoo_eps = consensus.trailing_eps if consensus is not None else None

    if not _diverges(template_eps, yahoo_eps):
        return ResolvedEps(
            eps_ttm=template_eps,
            currency=currency,
            source="twelvedata",
            detail=f"Template TTM EPS ({symbol}{template_eps:.2f}), as of {latest_date}",
        )

    if yahoo_eps is not None and math.isfinite(yahoo_eps) and yahoo_eps > 0:
        quarter_note = (
            f" (most recent quarter: {consensus.most_recent_quarter_end_date})"
            if consensus is not None and consensus.most_recent_quarter_end_date
            else ""
        )
        return ResolvedEps(
            eps_ttm=yahoo_eps,
            currency=currency,
            source="yahoo-fallback",
            detail=(
                f"Yahoo Finance trailing EPS ({symbol}{yahoo_eps:.2f}){quarter_note} — used "
                f"because the template's TTM EPS ({symbol}{template_eps:.2f}) diverged more "
                "than 5% from Yahoo's"
            ),
        )

    return ResolvedEps(
        eps_ttm=template_eps,
        currency=currency,
        source="twelvedata-stale-no-fallback",
        detail=(
            f"Template TTM EPS ({symbol}{template_eps:.2f}), as of {latest_date} — flagged as "
            "possibly stale (diverges more than 5% from Yahoo), but Yahoo's own figure "
            "isn't usable as a replacement"
        ),
    )


def _currency_symbol(currency: Currency) -> str:
    """Matches `charts/base.py`'s `currency_symbol()` convention (₪ for ILS, $
    otherwise) without importing from the charts slice — this module has no
    other reason to depend on it, and the mapping is a one-line constant."""
    return "₪" if currency == Currency.ILS else "$"


def _template_ttm_eps(fundamentals: CompanyFundamentals) -> Point | None:
    """The template's own most recent TTM EPS point (value *and* the date it
    actually covers), or `None` if the `eps` series is missing/unavailable.

    Returning the whole `Point` — not just its `Money` value — matters: the
    date `detail` reports must be the date of the TTM window actually used,
    not just the newest raw quarterly point, since `ttm_series` can skip a
    window (a gap in the raw series) and leave the latest *TTM* point dated
    earlier than the latest *raw* point.
    """
    eps_series = fundamentals.series.get("eps")
    if eps_series is None or not eps_series.available:
        return None
    ttm = ttm_series(eps_series, fundamentals.period)
    if not ttm.available or not ttm.points:
        return None
    return max(ttm.points, key=lambda point: point.date)


def _diverges(template_eps: float, yahoo_eps: float | None) -> bool:
    """Whether the two figures disagree by more than 5%, relative to Yahoo's
    figure (matching the original's `relativeDiff` convention of dividing by the
    reference/provider figure). `yahoo_eps == 0` can't support a relative
    comparison and is treated as "can't tell", not "diverges".
    """
    if yahoo_eps is None or not math.isfinite(yahoo_eps) or yahoo_eps == 0:
        return False
    if not math.isfinite(template_eps):
        return False
    relative_diff = abs(template_eps - yahoo_eps) / abs(yahoo_eps)
    return relative_diff > _STALE_DIVERGENCE_THRESHOLD
