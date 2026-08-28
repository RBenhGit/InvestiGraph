import argparse
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path

from financial_charts import chart_support, config
from financial_charts.cache.store import TemplateCache
from financial_charts.charts.catalog import get_chart
from financial_charts.charts.registry import (
    CUSTOM_CHART_SET_PREFIX,
    get_chart_set,
    register_chart_set,
)
from financial_charts.dashboard.render import write_output
from financial_charts.sources.base import (
    Capability,
    MissingCredentials,
    SourceUnavailable,
    TickerNotFound,
    UnsupportedPeriod,
)
from financial_charts.sources.commission import (
    capability_module_path,
    commission,
    is_degenerate,
    write_capability_module,
)
from financial_charts.sources.market import is_valid_ticker, market_of, normalize_ticker
from financial_charts.sources.ranges import RANGES
from financial_charts.sources.registry import (
    get_capability,
    get_source,
    registered_sources,
)
from financial_charts.sources.validation import check_request, require_supported_period
from financial_charts.sources.verify import reconcile
from financial_charts.template.models import CompanyFundamentals, Market, Period


def _add_render_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("ticker", help="e.g. AAPL (US) or TEVA.TA (TASE)")
    parser.add_argument(
        "--source", default=None, help="overrides the DATA_SOURCE env var"
    )
    parser.add_argument(
        "--period",
        choices=[p.value for p in Period],
        default=config.DEFAULT_PERIOD,
        help="ttm is modeled but not yet supported by any registered source",
    )
    parser.add_argument(
        "--range", type=str.lower, choices=RANGES, default=config.DEFAULT_RANGE
    )
    parser.add_argument(
        "--chart-set", dest="chart_set", default=config.DEFAULT_CHART_SET
    )
    parser.add_argument(
        "--charts",
        default=None,
        help="comma-separated chart ids overriding --chart-set, e.g. price,eps,margins",
    )
    parser.add_argument(
        "--out", default=None, help="output path (.html, .png, or .pdf)"
    )


def _dedup_chart_ids(raw_ids: list[str]) -> list[str]:
    """Strip, drop empties, and drop duplicates, keeping first-seen order.

    First-seen order is preserved so a user's `--charts eps,price` renders in
    the order they asked for; a registered set's name is still built from the
    sorted ids so equivalent selections (any order) share one registry entry
    instead of growing `_CHART_SETS` once per ordering.
    """
    seen: set[str] = set()
    ids: list[str] = []
    for raw in raw_ids:
        chart_id = raw.strip()
        if chart_id and chart_id not in seen:
            seen.add(chart_id)
            ids.append(chart_id)
    return ids


def _resolve_chart_set_name(args: argparse.Namespace) -> str | None:
    """Return the chart set name to render, or None with an error already printed.

    `--charts` builds and registers an ad-hoc set from catalog chart ids,
    overriding `--chart-set`; otherwise the named set is used as-is.
    """
    if not args.charts:
        try:
            get_chart_set(args.chart_set)
        except KeyError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return None
        return args.chart_set

    chart_ids = _dedup_chart_ids(args.charts.split(","))
    if not chart_ids:
        print("error: no charts specified", file=sys.stderr)
        return None

    try:
        charts = [get_chart(chart_id) for chart_id in chart_ids]
    except KeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return None

    # Registered permanently in the shared _CHART_SETS registry (never evicted)
    # keyed by the sorted id set, so repeat/reordered requests for the same
    # selection reuse one entry — bounded by the catalog's size (at most
    # 2^N - 1 distinct subsets for N registered charts), which only grows
    # through reviewed commits, not user input.
    chart_set_name = CUSTOM_CHART_SET_PREFIX + ",".join(sorted(chart_ids))
    register_chart_set(chart_set_name, charts)
    return chart_set_name


def _fetch_with_cache_fallback(
    adapter,
    cache: TemplateCache,
    ticker: str,
    source_name: str,
    market: Market,
    period: Period,
    range_: str,
) -> CompanyFundamentals:
    today = date.today()
    cached = cache.get(ticker, source_name, period, range_, today)
    if cached is not None:
        return cached

    try:
        fundamentals = adapter.fetch(ticker, market, period, range_)
    except SourceUnavailable:
        stale = cache.latest(ticker, source_name, period, range_)
        if stale is None:
            raise
        stale.source_limits.append(
            "network/API unavailable; showing a stale cached page"
        )
        return stale

    cache.put(ticker, source_name, period, range_, today, fundamentals)
    return fundamentals


def _run_render(args: argparse.Namespace) -> int:
    ticker = args.ticker
    if not is_valid_ticker(ticker):
        print(f"error: invalid ticker: {ticker!r}", file=sys.stderr)
        return 1
    ticker = normalize_ticker(ticker)

    market = market_of(ticker)
    period = Period(args.period)
    source_name = args.source or config.data_source_name()

    chart_set_name = _resolve_chart_set_name(args)
    if chart_set_name is None:
        return 1

    try:
        adapter = get_source(source_name)
    except (KeyError, MissingCredentials) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    try:
        require_supported_period(adapter.capability(), period)
    except UnsupportedPeriod as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    cache = TemplateCache()
    try:
        fundamentals = _fetch_with_cache_fallback(
            adapter, cache, ticker, source_name, market, period, args.range
        )
    except TickerNotFound:
        print(f"error: ticker not found: {ticker}", file=sys.stderr)
        return 1
    except SourceUnavailable as exc:
        print(
            f"error: source unavailable and no cache to fall back to: {exc}",
            file=sys.stderr,
        )
        return 1

    fundamentals.source_limits.extend(
        limit
        for limit in check_request(adapter.capability(), market, period, args.range)
        if limit not in fundamentals.source_limits
    )
    fundamentals.source_limits.extend(
        limit
        for limit in chart_support.capability_limits(
            get_chart_set(chart_set_name), adapter.capability()
        )
        if limit not in fundamentals.source_limits
    )

    out_path = Path(args.out) if args.out else Path("out") / f"{ticker}.html"
    try:
        write_output(fundamentals, out_path, chart_set_name)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {out_path}")
    return 0


def _add_verify_source_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "verify-source",
        help="Reconcile a source's declared Capability against a live fetch",
    )
    parser.add_argument(
        "name", help="registered source name, e.g. yfinance or twelvedata"
    )
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--market", choices=[m.value for m in Market], default=None)
    parser.add_argument(
        "--period", choices=[p.value for p in Period], default=Period.ANNUAL.value
    )
    parser.add_argument("--range", default="5y")


def _run_verify_source(args: argparse.Namespace) -> int:
    market = Market(args.market) if args.market else market_of(args.ticker)
    period = Period(args.period)

    adapter = get_source(args.name)
    report = reconcile(adapter, args.ticker, market, period, args.range)

    print(
        f"verify-source: {args.name} / {args.ticker} ({market.value}, {period.value}, {args.range})"
    )
    print(
        f"  declared-but-missing metrics (mismatch): {report.missing_metrics or 'none'}"
    )
    print(
        f"  undeclared extras (info):                {report.undeclared_extras or 'none'}"
    )
    print(
        f"  unit/currency warnings:                  {report.unit_warnings or 'none'}"
    )
    print(f"  history points per metric:                {report.history_points}")
    print(
        f"  declared-vs-actual history depth:        {report.history_warnings or 'none'}"
    )

    if report.has_mismatch:
        print("RESULT: mismatch found", file=sys.stderr)
        return 1
    print("RESULT: clean")
    return 0


def _add_capabilities_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "capabilities",
        help="Print a registered source's declared Capability (offline, no credentials)",
    )
    parser.add_argument(
        "name", nargs="?", default=None, help="registered source name; omit for all"
    )
    parser.add_argument(
        "--matrix",
        action="store_true",
        help="print a metric x source availability table instead",
    )


def _format_capability(name: str, capability: Capability) -> str:
    markets = ", ".join(sorted(m.value for m in capability.markets))
    periods = ", ".join(sorted(p.value for p in capability.periods))
    history = ", ".join(
        f"{period.value}={years}y"
        for period, years in sorted(
            capability.max_history.items(), key=lambda kv: kv[0].value
        )
    )
    metrics = ", ".join(sorted(capability.metrics))
    return (
        f"capabilities: {name}\n"
        f"  markets:      {markets}\n"
        f"  periods:      {periods}\n"
        f"  max_history:  {history}\n"
        f"  metrics:      {metrics}"
    )


def _format_matrix(names: list[str]) -> str:
    capabilities = {name: get_capability(name) for name in names}
    all_metrics = sorted(set().union(*(c.metrics for c in capabilities.values())))
    metric_col = max(len(m) for m in all_metrics) + 2
    source_col = max(len(n) for n in names) + 2

    lines = ["capability matrix (metric x source):"]
    lines.append(" " * metric_col + "".join(n.ljust(source_col) for n in names))
    for metric in all_metrics:
        row = metric.ljust(metric_col)
        for name in names:
            row += ("x" if metric in capabilities[name].metrics else "-").ljust(
                source_col
            )
        lines.append(row)
    return "\n".join(lines)


def _run_capabilities(args: argparse.Namespace) -> int:
    if args.name:
        try:
            get_capability(args.name)
        except KeyError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        names = [args.name]
    else:
        names = registered_sources()

    if args.matrix:
        print(_format_matrix(names))
    else:
        print(
            "\n\n".join(
                _format_capability(name, get_capability(name)) for name in names
            )
        )
    return 0


def _add_commission_source_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "commission-source",
        help=(
            "Probe a registered source live across sample tickers and generate "
            "sources/<name>/capability.py from what's actually returned"
        ),
    )
    parser.add_argument(
        "name", help="registered source name, e.g. yfinance or twelvedata"
    )
    parser.add_argument("--range", default="max")


def _run_commission_source(args: argparse.Namespace) -> int:
    try:
        adapter = get_source(args.name)
    except (KeyError, MissingCredentials) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    certificate = commission(adapter, args.name, range_=args.range)

    print(f"commission-source: {args.name} (generated {certificate.generated_at})")
    print()
    print("samples:")
    for sample in certificate.samples:
        status = "ok" if sample.ok else f"FAILED ({sample.error})"
        metrics = ", ".join(sorted(sample.available_metrics)) or "none"
        print(
            f"  {sample.market.value:<5} {sample.company_type:<10} "
            f"{sample.ticker:<10} {sample.period.value:<10} {status:<24} "
            f"metrics: {metrics}"
        )
    print()
    print(_format_capability(args.name, certificate.capability))
    print()

    if is_degenerate(certificate):
        print(
            "error: every sample failed — this looks like a wholesale outage, "
            "not a real capability change; refusing to overwrite capability.py",
            file=sys.stderr,
        )
        return 1

    path = capability_module_path(args.name)
    print(f"overwriting {path} — review the diff before committing")
    write_capability_module(certificate)
    print(f"wrote {path}")
    return 0


_COMMANDS = ("render", "verify-source", "capabilities", "commission-source")

_DISPATCH: dict[str, Callable[[argparse.Namespace], int]] = {
    "render": _run_render,
    "verify-source": _run_verify_source,
    "capabilities": _run_capabilities,
    "commission-source": _run_commission_source,
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="financial_charts")
    subparsers = parser.add_subparsers(dest="command", required=True)

    render_parser = subparsers.add_parser(
        "render", help="Render a ticker's dashboard (the default command)"
    )
    _add_render_arguments(render_parser)

    _add_verify_source_parser(subparsers)
    _add_capabilities_parser(subparsers)
    _add_commission_source_parser(subparsers)

    return parser


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    # `render` is the implicit default command, so `financial_charts AAPL ...`
    # keeps working without typing `render` explicitly; `-h`/`--help` and the
    # three other command names are left alone so top-level `--help` still
    # lists every command. This can't fully disambiguate a mistyped subcommand
    # from an unusual ticker string (e.g. `financial_charts capabilites` is
    # parsed as ticker "capabilites", not an error) — fully closing that would
    # require a mandatory verb, breaking the documented
    # `financial_charts <TICKER> ...` CLI. What this does fix: one real
    # argparse parser (consistent errors, full --help) instead of three
    # hand-rolled throwaway ones.
    first = argv[0] if argv else None
    if first not in (*_COMMANDS, "-h", "--help"):
        argv = ["render", *argv]

    args = _build_parser().parse_args(argv)
    return _DISPATCH[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
