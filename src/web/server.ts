import { fileURLToPath } from 'node:url';
import path from 'node:path';
import Fastify from 'fastify';
import fastifyStatic from '@fastify/static';
import { fetchStockData } from '../data/twelvedata';
import { fetchAnalystConsensus } from '../data/yahoo';
import { safeTickerSegment } from '../data/cache';
import { resolveEpsWithFallback } from '../data/resolveEps';
import { calculateLynchValue } from '../valuation/lynch';
import { calculateRuleOneValue } from '../valuation/ruleOne';
import { saveValuation, getHistory, deleteValuation, getAllLatestValuations, type SaveValuationInput } from '../history';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
// 3000/3001/3100 are already claimed by other projects on this machine (stock_vision, etc.) —
// default to a port that doesn't collide.
const PORT = Number(process.env.PORT) || 3210;

interface ValuateRequestBody {
  ticker: string;
  epsOverride?: number;
  growthRatePercent?: number | null;
  exitPeMultiple: number;
  requiredReturnPercent: number;
  years: number;
  // MoS is a single value shared across all three scenarios (set once in the top assumptions
  // row) — there is no per-scenario MoS override.
  mosPercent?: number;
  // Bear/bull scenarios each have their own independent growth rate and their own exit-P/E /
  // required-return (see the "scenario-assumptions" rows in index.html) rather than being
  // derived from the base scenario or hardcoded — fall back to deriving from effectiveGrowth
  // (0.75x/1.25x) only when the frontend omits them (e.g. an older client).
  bearGrowthRatePercent?: number | null;
  bearExitPeMultiple?: number;
  bearRequiredReturnPercent?: number;
  bullGrowthRatePercent?: number | null;
  bullExitPeMultiple?: number;
  bullRequiredReturnPercent?: number;
  forceRefresh?: boolean;
}

export function buildServer() {
  const fastify = Fastify();

  fastify.register(fastifyStatic, {
    root: path.join(__dirname, 'public'),
  });

  fastify.post<{ Body: ValuateRequestBody }>('/api/valuate', async (request, reply) => {
    // ValuateRequestBody is a TypeScript interface — compile-time only — so nothing stops a
    // caller from POSTing no body at all, or a literal JSON `null`. Destructuring straight off
    // request.body in that case threw ("Cannot destructure property 'ticker' of ... as it is
    // undefined/null") before any of the guards below ever ran, surfacing as an unhandled 500.
    const rawBody: unknown = request.body;
    if (typeof rawBody !== 'object' || rawBody === null) {
      return reply.status(400).send({
        ok: false,
        error: {
          type: 'INSUFFICIENT_DATA',
          ticker: '',
          reason: 'request body is required and must be a JSON object',
        },
      });
    }

    const {
      ticker,
      epsOverride,
      growthRatePercent,
      exitPeMultiple,
      requiredReturnPercent,
      years,
      mosPercent,
      bearGrowthRatePercent,
      bearExitPeMultiple,
      bearRequiredReturnPercent,
      bullGrowthRatePercent,
      bullExitPeMultiple,
      bullRequiredReturnPercent,
      forceRefresh,
    } = rawBody as ValuateRequestBody;

    // Same interface-is-compile-time-only gap: nothing stops a caller from POSTing a missing/
    // null/non-string ticker. Without this guard it reached fetchStockData and threw inside the
    // data layer, surfacing as an unhandled 500 with raw internal text ("ticker.toUpperCase is
    // not a function") instead of the typed { ok: false, error } shape every other failure path
    // in this codebase returns.
    if (typeof ticker !== 'string' || ticker.trim() === '') {
      return reply.status(400).send({
        ok: false,
        error: {
          type: 'INSUFFICIENT_DATA',
          ticker: typeof ticker === 'string' ? ticker : '',
          reason: 'ticker is required and must be a non-empty string',
        },
      });
    }

    // safeTickerSegment is the exact same rule src/data/cache.ts uses to build cache filenames.
    // Validating with it here — rather than just checking non-blank — guarantees any ticker that
    // clears this boundary can also be cached; previously a ticker accepted here but rejected by
    // the cache's stricter charset (e.g. containing a space) triggered a real live API call on
    // every single request, with caching silently never engaging and nothing surfacing why. This
    // also gives us the normalized (trimmed, upper-cased) form to use everywhere below instead
    // of forwarding whatever whitespace/casing the caller happened to send.
    const normalizedTicker = safeTickerSegment(ticker.trim());
    if (normalizedTicker === null) {
      return reply.status(400).send({
        ok: false,
        error: {
          type: 'INSUFFICIENT_DATA',
          ticker: ticker.trim(),
          reason: 'ticker must contain only letters, digits, and . : - characters (1-20 chars)',
        },
      });
    }

    // twelvedata is the required source — a failure there fails the whole request (see below).
    // yahoo (analyst consensus/price targets) is supplementary and independently fetched in
    // parallel: its failure must never take down a valuation that only needed twelvedata's
    // data, so it degrades to `null` rather than being awaited into the failure path.
    const [result, analystConsensusResult] = await Promise.all([
      fetchStockData(normalizedTicker, { forceRefresh }),
      fetchAnalystConsensus(normalizedTicker, { forceRefresh }).catch(() => null),
    ]);

    if (!result.ok) {
      const status = result.error.type === 'NOT_FOUND' ? 404 : 400;
      return reply.status(status).send({ ok: false, error: result.error });
    }

    const { data } = result;
    const analystConsensus =
      analystConsensusResult && analystConsensusResult.ok ? analystConsensusResult.data : null;
    // Only second-guesses epsTtm when Twelve Data's own figure looked stale (staleTtmWarning);
    // a healthy figure is never overridden. Yahoo's trailingEps is a whole-TTM figure (not
    // decomposable into quarters), so this is a full replacement, not a per-quarter splice —
    // see resolveEps.ts. An explicit epsOverride from the frontend still wins over both.
    const resolvedEps = resolveEpsWithFallback(data, analystConsensus);
    const effectiveEps =
      typeof epsOverride === 'number' && epsOverride > 0 ? epsOverride : resolvedEps.epsTtm;

    let effectiveGrowth = typeof growthRatePercent === 'number' ? growthRatePercent : null;

    // Seed the growth rate automatically if not provided by the frontend. Must match the CLI's
    // fallback chain exactly (see src/cli/index.ts) — no extra cap, no defaulting to 0 when
    // every source is null. Defaulting to 0 would silently turn "no growth data available" into
    // a fabricated $0 fair value instead of the MISSING_GROWTH_RATE error the valuation
    // functions are designed to surface.
    if (effectiveGrowth === null) {
      effectiveGrowth =
        data.growth.analystEstimate5yPercent ??
        data.growth.historical3yPercent ??
        data.growth.historical1yPercent ??
        null;
    }

    // Calculate base scenario
    const lynchBase = calculateLynchValue(effectiveEps, effectiveGrowth);
    const ruleOneBase = calculateRuleOneValue(
      effectiveEps,
      effectiveGrowth,
      exitPeMultiple,
      requiredReturnPercent,
      years,
      mosPercent ?? 0,
    );

    // Calculate bear scenario. Growth is now fully independent, editable per scenario (the
    // user's own bear-row Growth input) — it is only ever auto-derived from the base
    // scenario's growth (effectiveGrowth * 0.75) when the frontend omits the field entirely
    // (e.g. an older client). Exit P/E and required return likewise come from the user's own
    // bear-row inputs — never hardcoded. MoS is shared across all three scenarios (a single
    // top-level value, no per-scenario override).
    const bearGrowth =
      typeof bearGrowthRatePercent === 'number'
        ? bearGrowthRatePercent
        : effectiveGrowth !== null
          ? Number((effectiveGrowth > 0 ? effectiveGrowth * 0.75 : effectiveGrowth - 3).toFixed(2))
          : null;
    const lynchBear = calculateLynchValue(effectiveEps, bearGrowth);
    const ruleOneBear = calculateRuleOneValue(
      effectiveEps,
      bearGrowth,
      bearExitPeMultiple ?? 10,
      bearRequiredReturnPercent ?? 15,
      years,
      mosPercent ?? 0,
    );

    // Calculate bull scenario — same principle: growth defaults to deriving from the base
    // scenario (effectiveGrowth * 1.25) only when the frontend omits the field; exit P/E and
    // required return come from the user's bull-row inputs; MoS is the shared top-level value.
    const bullGrowth =
      typeof bullGrowthRatePercent === 'number'
        ? bullGrowthRatePercent
        : effectiveGrowth !== null
          ? Number((effectiveGrowth > 0 ? effectiveGrowth * 1.25 : effectiveGrowth + 3).toFixed(2))
          : null;
    const lynchBull = calculateLynchValue(effectiveEps, bullGrowth);
    const ruleOneBull = calculateRuleOneValue(
      effectiveEps,
      bullGrowth,
      bullExitPeMultiple ?? 20,
      bullRequiredReturnPercent ?? 12,
      years,
      mosPercent ?? 0,
    );

    return reply.status(200).send({
      ok: true,
      data,
      effectiveEps,
      // Provenance of effectiveEps, for the UI to label the number honestly instead of silently
      // showing a Yahoo-sourced figure as if it were Twelve Data's. `null` when epsOverride won
      // (a user-typed value has no "source" to report). See resolveEps.ts.
      epsSource: typeof epsOverride === 'number' && epsOverride > 0 ? null : resolvedEps.source,
      effectiveGrowth,
      // The growth rate actually used for bear/bull, echoed back regardless of whether lynch/
      // ruleOne succeeded for that scenario — same reasoning as effectiveGrowth above. Without
      // this, the frontend had to reverse-engineer the value from lynch.bear.inputs/
      // ruleOne.bear.inputs, which don't exist on a failed ValuationResult at all: if ruleOne
      // fails for an unrelated reason (e.g. an emptied exit-P/E) while lynch simultaneously
      // fails for a different unrelated reason (e.g. this same negative growth rate), neither
      // result carries the number that was actually computed and used server-side, even though
      // one really was.
      bearGrowth,
      bullGrowth,
      lynch: {
        base: lynchBase,
        bear: lynchBear,
        bull: lynchBull,
      },
      ruleOne: {
        base: ruleOneBase,
        bear: ruleOneBear,
        bull: ruleOneBull,
      },
      analystConsensus,
      // Human-readable note on which source effectiveEps actually reflects, and any relevant
      // asOf/quarter dates — see resolveEps.ts. Redundant with epsSource for a machine, but
      // saves the frontend from re-deriving the same message from raw fields.
      epsSourceDetail: resolvedEps.detail,
    });
  });

  fastify.get<{ Querystring: { ticker?: string; evaluator?: string } }>('/api/history', async (request, reply) => {
    const { ticker, evaluator } = request.query;
    const result = await getHistory(ticker, undefined, evaluator);
    if (!result.ok) {
      return reply.status(500).send(result);
    }
    return reply.status(200).send(result);
  });

  fastify.get('/api/valuations', async (request, reply) => {
    const result = await getAllLatestValuations();
    if (!result.ok) {
      return reply.status(500).send(result);
    }
    return reply.status(200).send(result);
  });

  fastify.post<{ Body: SaveValuationInput & { evaluator?: string } }>('/api/history', async (request, reply) => {
    const result = await saveValuation(request.body);
    if (!result.ok) {
      const status = result.error.type === 'INVALID_INPUT' ? 400 : 500;
      return reply.status(status).send(result);
    }
    return reply.status(201).send(result);
  });

  fastify.delete<{ Params: { id: string }; Querystring: { evaluator?: string } }>('/api/history/:id', async (request, reply) => {
    const { id } = request.params;
    const { evaluator } = request.query;
    const result = await deleteValuation(id, undefined, evaluator);
    if (!result.ok) {
      const status = result.error.type === 'NOT_FOUND' ? 404 : 500;
      return reply.status(status).send(result);
    }
    return reply.status(200).send(result);
  });

  return fastify;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const fastify = buildServer();
  // Keep the app private; Tailscale Serve provides the authenticated HTTPS entry point.
  fastify.listen({ port: PORT, host: '127.0.0.1' }, (err, address) => {
    if (err) {
      fastify.log.error(err);
      process.exit(1);
    }
    console.log(`Listening on ${address}`);
  });
}
