from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

# Deliberate exception to the project's one-way source-adapter -> template ->
# display pipeline: this is developer tooling, not a render, and reading the
# catalog here avoids a second, hand-maintained metric list that would drift
# from the real one (see candidate_metrics() below).
from financial_charts.charts.catalog import available_charts
from financial_charts.sources.base import (
    Capability,
    DataSource,
    SourceUnavailable,
    TickerNotFound,
)
from financial_charts.sources.ranges import approx_years
from financial_charts.template.models import Market, Period

# Illustrative sample tickers spanning company types per market, chosen so a
# source's capability isn't judged from one ticker's quirks (a bank's
# statements are shaped differently than a large-cap's or a small-cap's —
# e.g. "revenue" doesn't always map cleanly onto a bank's income statement).
# Review and adjust before commissioning for real: company classifications
# and ticker validity drift over time and this module has no way to verify
# them independently — it only reflects what was true when it was written.
SAMPLE_TICKERS: dict[Market, dict[str, str]] = {
    Market.US: {
        "bank": "JPM",
        "large_cap": "AAPL",
        "small_cap": "OXM",
    },
    Market.TASE: {
        "bank": "POLI.TA",
        "large_cap": "TEVA.TA",
        "small_cap": "ORL.TA",
    },
}

_DEFAULT_PERIODS: tuple[Period, ...] = (Period.ANNUAL, Period.QUARTERLY)


@dataclass(frozen=True)
class SampleResult:
    market: Market
    company_type: str
    ticker: str
    period: Period
    ok: bool
    available_metrics: frozenset[str]
    error: str | None = None


@dataclass(frozen=True)
class CommissionCertificate:
    source_name: str
    generated_at: date
    samples: tuple[SampleResult, ...]
    capability: Capability


def candidate_metrics() -> list[str]:
    """Every metric a registered chart requires — the universe commissioning probes for.

    Derived from the chart catalog rather than hardcoded, so a new chart's
    metric requirement is automatically covered by future commissioning runs.
    A derived quantity's own id (e.g. "fcf_margin") never appears here — only
    its base inputs do, since a source never supplies a derived value directly.
    """
    return sorted(
        {
            metric_id
            for chart in available_charts()
            for metric_id in chart.required_metrics
        }
    )


def is_degenerate(certificate: CommissionCertificate) -> bool:
    """Whether `certificate` looks like a wholesale-failed probing run.

    `samples` non-empty but `markets` empty means every sample that was
    actually attempted failed outright (e.g. the whole live API was down for
    the run) — as opposed to `samples` being empty because no tickers were
    configured for any market, which is a deliberate skip, not a failure.
    """
    return bool(certificate.samples) and not certificate.capability.markets


def commission(
    adapter: DataSource,
    source_name: str,
    sample_tickers: dict[Market, dict[str, str]] = SAMPLE_TICKERS,
    periods: tuple[Period, ...] = _DEFAULT_PERIODS,
    range_: str = "max",
) -> CommissionCertificate:
    """Probe `adapter` live across a sample of tickers per market and company
    type, and derive a `Capability` from what's actually returned.

    Deliberately never consults `adapter.capability()` — the point is to
    discover reality independent of whatever the current declaration claims,
    since that declaration may be exactly what's stale or wrong.

    A metric is declared supported only if every sample (every market,
    company type, and period) had it available — conservative by design, so
    one ticker type's gap (e.g. a bank lacking a clean revenue line item)
    correctly keeps a metric out of the declaration instead of being averaged
    away by a large-cap sample that happens to have it. A market is declared
    supported only if every sample in it fetched successfully and returned a
    `price` series — the one bare-minimum guarantee a market needs to be
    usable at all.

    Only the two protocol-documented failure modes (`TickerNotFound`,
    `SourceUnavailable`) are handled; anything else propagates, since an
    unexpected exception here is a bug to investigate, not a declared gap.
    """
    candidates = candidate_metrics()
    metrics: set[str] | None = None
    max_history: dict[Period, int] = {}
    samples: list[SampleResult] = []
    markets: set[Market] = set()

    for market, tickers_by_type in sample_tickers.items():
        if not tickers_by_type:
            # A market with no sample tickers was never actually probed —
            # skip it rather than vacuously declaring it supported.
            continue
        market_ok = True
        for company_type, ticker in tickers_by_type.items():
            for period in periods:
                try:
                    fundamentals = adapter.fetch(ticker, market, period, range_)
                except (TickerNotFound, SourceUnavailable) as exc:
                    market_ok = False
                    samples.append(
                        SampleResult(
                            market=market,
                            company_type=company_type,
                            ticker=ticker,
                            period=period,
                            ok=False,
                            available_metrics=frozenset(),
                            error=str(exc),
                        )
                    )
                    continue

                available = frozenset(
                    metric_id
                    for metric_id in candidates
                    if (series := fundamentals.series.get(metric_id)) is not None
                    and series.available
                )
                metrics = available if metrics is None else (metrics & available)
                if "price" not in available:
                    market_ok = False

                for metric_id in available:
                    years = approx_years(
                        period, len(fundamentals.series[metric_id].points)
                    )
                    max_history[period] = (
                        years
                        if period not in max_history
                        else min(max_history[period], years)
                    )

                samples.append(
                    SampleResult(
                        market=market,
                        company_type=company_type,
                        ticker=ticker,
                        period=period,
                        ok=True,
                        available_metrics=available,
                    )
                )

        if market_ok:
            markets.add(market)

    capability = Capability(
        markets=markets,
        periods=set(periods),
        max_history=max_history,
        metrics=metrics or set(),
    )
    return CommissionCertificate(
        source_name=source_name,
        generated_at=date.today(),
        samples=tuple(samples),
        capability=capability,
    )


def _capability_module_source(certificate: CommissionCertificate) -> str:
    capability = certificate.capability
    markets_repr = (
        "{"
        + ", ".join(
            f"Market.{m.name}" for m in sorted(capability.markets, key=lambda m: m.name)
        )
        + "}"
    )
    periods_repr = (
        "{"
        + ", ".join(
            f"Period.{p.name}" for p in sorted(capability.periods, key=lambda p: p.name)
        )
        + "}"
    )
    history_repr = (
        "{"
        + ", ".join(
            f"Period.{p.name}: {years}"
            for p, years in sorted(
                capability.max_history.items(), key=lambda kv: kv[0].name
            )
        )
        + "}"
    )
    # repr() (not manual quoting) so a metric id containing a quote or other
    # special character still produces syntactically valid Python — unlike
    # markets/periods above, these strings aren't drawn from a closed enum.
    metrics_repr = "{" + ", ".join(repr(m) for m in sorted(capability.metrics)) + "}"

    return (
        "from financial_charts.sources.base import Capability\n"
        "from financial_charts.template.models import Market, Period\n"
        "\n"
        f"# Generated by `commission-source` on {certificate.generated_at.isoformat()},"
        " probed live against\n"
        "# the sample tickers in sources/commission.py's SAMPLE_TICKERS — see the printed\n"
        "# certificate for exactly which tickers/periods this was derived from. Review\n"
        "# before committing: this is a human-owned contract (see CLAUDE.md), not a\n"
        "# runtime probe — commissioning only drafts it faster.\n"
        "CAPABILITY = Capability(\n"
        f"    markets={markets_repr},\n"
        f"    periods={periods_repr},\n"
        f"    max_history={history_repr},\n"
        f"    metrics={metrics_repr},\n"
        ")\n"
    )


def capability_module_path(source_name: str, base_dir: Path | None = None) -> Path:
    """Where commissioning would write source_name's capability.py.

    Exposed separately from write_capability_module so a caller can print an
    explicit "about to overwrite X" line before the write actually happens.
    """
    root = base_dir if base_dir is not None else Path(__file__).resolve().parent
    return root / source_name / "capability.py"


def write_capability_module(
    certificate: CommissionCertificate, base_dir: Path | None = None
) -> Path:
    """Write the generated declaration to sources/<name>/capability.py, overwriting it.

    `base_dir` defaults to this module's own package directory (the real
    `sources/` tree) and is overridable only so tests can target a tmp_path
    instead of the real source tree.
    """
    path = capability_module_path(certificate.source_name, base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_capability_module_source(certificate))
    return path
