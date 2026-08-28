from dataclasses import dataclass

from flask import Flask, Response, jsonify, render_template, request

from financial_charts import chart_support, config
from financial_charts.charts.catalog import available_charts, get_chart
from financial_charts.charts.registry import (
    CUSTOM_CHART_SET_PREFIX,
    get_chart_set,
    register_chart_set,
    registered_chart_sets,
)
from financial_charts.dashboard.render import render_html
from financial_charts.sources.base import (
    MissingCredentials,
    SourceUnavailable,
    TickerNotFound,
    UnsupportedPeriod,
)
from financial_charts.sources.market import is_valid_ticker, normalize_ticker
from financial_charts.sources.ranges import RANGES
from financial_charts.sources.registry import get_source, registered_sources
from financial_charts.sources.validation import require_supported_period
from financial_charts.template.models import CompanyFundamentals, Period
from financial_charts.web.chart_data import ChartDataResponse, build_chart_specs
from financial_charts.web.chart_set_store import ChartSetStore
from financial_charts.web.service import load_fundamentals

# Submitted values are still validated by the real get_source/get_chart_set inside the
# render path, so an unsupported value produces a proper error, not a blank.
PERIODS = [p.value for p in Period]


def _dedup_chart_ids(raw_ids: list[str]) -> list[str]:
    """Strip, drop empties, and drop duplicates, keeping first-seen order.

    Mirrors __main__._dedup_chart_ids (this module and the CLI compose the
    same published functions independently rather than sharing private code,
    matching web/service.py's existing convention). Preventing duplicate ids
    from reaching register_chart_set keeps the generated set name — and the
    permanent, never-evicted _CHART_SETS entry it creates — bounded by the
    catalog's size rather than growing once per repeated/reordered request.
    """
    seen: set[str] = set()
    ids: list[str] = []
    for raw in raw_ids:
        chart_id = raw.strip()
        if chart_id and chart_id not in seen:
            seen.add(chart_id)
            ids.append(chart_id)
    return ids


@dataclass
class _RenderError(Exception):
    status: int
    message: str


def _resolve_request() -> tuple[CompanyFundamentals, str]:
    """Validate the request query params, fetch fundamentals, and merge capability limits.

    Shared by `/render` and `/chart-data` so the two response formats can't drift
    in what they accept or reject. Raises `_RenderError` on any invalid input or
    fetch failure; the caller decides how to render that into its own response shape.
    """
    ticker = (request.args.get("ticker") or "").strip()
    if not ticker:
        raise _RenderError(400, "Enter a ticker to render.")
    if not is_valid_ticker(ticker):
        raise _RenderError(400, f"Invalid ticker: {ticker}")
    ticker = normalize_ticker(ticker)

    source_name = request.args.get("source") or config.data_source_name()
    period_value = request.args.get("period") or config.DEFAULT_PERIOD
    if period_value not in PERIODS:
        raise _RenderError(400, f"Unsupported period: {period_value}")
    range_ = (request.args.get("range") or config.DEFAULT_RANGE).lower()
    if range_ not in RANGES:
        raise _RenderError(400, f"Unsupported range: {range_}")

    chart_ids = _dedup_chart_ids(request.args.getlist("charts"))
    if chart_ids:
        try:
            charts = [get_chart(chart_id) for chart_id in chart_ids]
        except KeyError as exc:
            raise _RenderError(400, str(exc).strip('"')) from exc
        # Registering here depends on the dev server's threaded=False
        # (web/__main__.py) so no two requests interleave a register and
        # a read of a different selection — see the memory note on this
        # pattern if that assumption ever changes (e.g. threaded=True or
        # a multi-worker WSGI deployment).
        chart_set = CUSTOM_CHART_SET_PREFIX + ",".join(sorted(chart_ids))
        register_chart_set(chart_set, charts)
    else:
        chart_set = request.args.get("chart_set") or config.DEFAULT_CHART_SET
        try:
            get_chart_set(chart_set)
        except KeyError as exc:
            raise _RenderError(400, str(exc).strip('"')) from exc

    # Resolved here (not inside load_fundamentals) so an unsupported period
    # is rejected before any fetch is attempted — same pre-flight gate the
    # CLI uses, kept independent rather than threaded through service.py.
    try:
        adapter = get_source(source_name)
    except KeyError as exc:
        raise _RenderError(400, str(exc).strip('"')) from exc
    except MissingCredentials as exc:
        raise _RenderError(400, str(exc)) from exc

    period = Period(period_value)
    try:
        require_supported_period(adapter.capability(), period)
    except UnsupportedPeriod as exc:
        raise _RenderError(400, str(exc)) from exc

    try:
        fundamentals = load_fundamentals(ticker, source_name, period, range_)
    except TickerNotFound as exc:
        raise _RenderError(404, f"Ticker not found: {ticker}") from exc
    except SourceUnavailable as exc:
        raise _RenderError(
            502, f"Source unavailable and no cache to fall back to: {exc}"
        ) from exc

    fundamentals.source_limits.extend(
        limit
        for limit in chart_support.capability_limits(
            get_chart_set(chart_set), adapter.capability()
        )
        if limit not in fundamentals.source_limits
    )
    return fundamentals, chart_set


def create_app(chart_set_store: ChartSetStore | None = None) -> Flask:
    app = Flask(__name__)
    store = chart_set_store or ChartSetStore()

    # Re-register any user-created chart sets saved in a previous run, so
    # restarting the server doesn't lose them. A chart id that no longer
    # resolves (e.g. removed from the catalog since it was saved) is skipped,
    # not a crash — same "declared gap, not a runtime surprise" posture as a
    # source's missing metric.
    for name, chart_ids in store.load().items():
        try:
            charts = [get_chart(chart_id) for chart_id in chart_ids]
        except KeyError:
            continue
        register_chart_set(name, charts)

    @app.get("/")
    def index() -> str:
        return render_template(
            "index.html",
            # Read live from the registries (not hand-maintained literals) so a
            # newly registered source or curated chart set appears in the
            # picker without a template/module change here.
            sources=registered_sources(),
            periods=PERIODS,
            ranges=RANGES,
            chart_sets=registered_chart_sets(),
            charts=available_charts(),
            chart_support={
                name: sorted(sources)
                for name, sources in chart_support.chart_support().items()
            },
            # Pre-check the checkbox picker with the default chart set's own
            # members — purely a UI starting point, doesn't change what an
            # empty-checkbox submit renders (that's still driven by the
            # Chart set dropdown, unaffected by this).
            default_chart_names={
                c.name for c in get_chart_set(config.DEFAULT_CHART_SET)
            },
            # Every registered set's own members, so the front end can re-sync
            # the checkbox picker whenever the Chart set dropdown changes,
            # not just at initial page load.
            chart_set_members={
                name: [c.name for c in get_chart_set(name)]
                for name in registered_chart_sets()
            },
            defaults={
                "source": config.data_source_name(),
                "period": config.DEFAULT_PERIOD,
                "range": config.DEFAULT_RANGE,
                "chart_set": config.DEFAULT_CHART_SET,
            },
        )

    @app.get("/render")
    def render():
        try:
            fundamentals, chart_set = _resolve_request()
        except _RenderError as exc:
            return render_template("error.html", message=exc.message), exc.status
        return render_html(fundamentals, chart_set)

    @app.get("/chart-data")
    def chart_data_route():
        try:
            fundamentals, chart_set = _resolve_request()
        except _RenderError as exc:
            return jsonify(error=exc.message), exc.status
        response = ChartDataResponse(
            ticker=fundamentals.ticker,
            market=fundamentals.market.value,
            currency=fundamentals.currency.value,
            source_limits=fundamentals.source_limits,
            charts=build_chart_specs(fundamentals, chart_set),
        )
        # Never flask.jsonify() a model with computed floats — it reproduces raw
        # NaN tokens (invalid JSON); Pydantic's model_dump_json() launders NaN to
        # null, which SMA warm-up periods and other computed ratios can produce.
        return Response(response.model_dump_json(), mimetype="application/json")

    @app.post("/chart-sets")
    def create_chart_set():
        # jsonify() is safe here (unlike /chart-data) — every field below is a
        # plain string/list of strings, never a computed float that could be NaN.
        name = (request.form.get("name") or "").strip()
        if not name:
            return jsonify(error="Enter a name for the chart set."), 400
        if name.startswith(CUSTOM_CHART_SET_PREFIX):
            return jsonify(
                error=f"Name can't start with {CUSTOM_CHART_SET_PREFIX!r}."
            ), 400
        if name in registered_chart_sets():
            return jsonify(error=f"A chart set named {name!r} already exists."), 400

        chart_ids = _dedup_chart_ids(request.form.getlist("charts"))
        if not chart_ids:
            return jsonify(error="Select at least one chart to save."), 400
        try:
            charts = [get_chart(chart_id) for chart_id in chart_ids]
        except KeyError as exc:
            return jsonify(error=str(exc).strip('"')), 400

        # Persist before registering: if the disk write fails, `name` never
        # goes live, so it isn't stuck "already exists" (blocking a retry)
        # while also not actually being saved anywhere.
        try:
            store.save(name, chart_ids)
        except OSError as exc:
            return jsonify(error=f"Could not save chart set: {exc}"), 500
        register_chart_set(name, charts)
        return jsonify(ok=True, name=name, charts=chart_ids)

    return app
