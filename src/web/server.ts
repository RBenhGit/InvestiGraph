import { fileURLToPath } from 'node:url';
import path from 'node:path';
import Fastify from 'fastify';
import fastifyStatic from '@fastify/static';
import { fetchStockData } from '../data/twelvedata';
import { fetchAnalystConsensus } from '../data/yahoo';
import { calculateLynchValue } from '../valuation/lynch';
import { calculateRuleOneValue } from '../valuation/ruleOne';
import {
  saveValuation,
  getHistory,
  deleteValuation,
  type SaveValuationInput,
} from '../history';

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
    } = request.body;

    // twelvedata is the required source — a failure there fails the whole request (see below).
    // yahoo (analyst consensus/price targets) is supplementary and independently fetched in
    // parallel: its failure must never take down a valuation that only needed twelvedata's
    // data, so it degrades to `null` rather than being awaited into the failure path.
    const [result, analystConsensusResult] = await Promise.all([
      fetchStockData(ticker, { forceRefresh }),
      fetchAnalystConsensus(ticker, { forceRefresh }).catch(() => null),
    ]);

    if (!result.ok) {
      const status = result.error.type === 'NOT_FOUND' ? 404 : 400;
      return reply.status(status).send({ ok: false, error: result.error });
    }

    const { data } = result;
    const effectiveEps = (typeof epsOverride === 'number' && epsOverride > 0) ? epsOverride : data.epsTtm;
    
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
    const bearGrowth = typeof bearGrowthRatePercent === 'number'
      ? bearGrowthRatePercent
      : (effectiveGrowth !== null
          ? Number((effectiveGrowth > 0 ? effectiveGrowth * 0.75 : effectiveGrowth - 3).toFixed(2))
          : null);
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
    const bullGrowth = typeof bullGrowthRatePercent === 'number'
      ? bullGrowthRatePercent
      : (effectiveGrowth !== null
          ? Number((effectiveGrowth > 0 ? effectiveGrowth * 1.25 : effectiveGrowth + 3).toFixed(2))
          : null);
    const lynchBull = calculateLynchValue(effectiveEps, bullGrowth);
    const ruleOneBull = calculateRuleOneValue(
      effectiveEps,
      bullGrowth,
      bullExitPeMultiple ?? 20,
      bullRequiredReturnPercent ?? 12,
      years,
      mosPercent ?? 0,
    );

    const analystConsensus =
      analystConsensusResult && analystConsensusResult.ok ? analystConsensusResult.data : null;

    return reply.status(200).send({ 
      ok: true, 
      data, 
      effectiveEps, 
      effectiveGrowth,
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
      analystConsensus 
    });
  });

  fastify.get<{ Querystring: { ticker?: string } }>('/api/history', async (request, reply) => {
    const { ticker } = request.query;
    const result = await getHistory(ticker);
    if (!result.ok) {
      return reply.status(500).send(result);
    }
    return reply.status(200).send(result);
  });

  fastify.post<{ Body: SaveValuationInput }>('/api/history', async (request, reply) => {
    const result = await saveValuation(request.body);
    if (!result.ok) {
      const status = result.error.type === 'INVALID_INPUT' ? 400 : 500;
      return reply.status(status).send(result);
    }
    return reply.status(201).send(result);
  });

  fastify.delete<{ Params: { id: string } }>('/api/history/:id', async (request, reply) => {
    const { id } = request.params;
    const result = await deleteValuation(id);
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
  // Bind to all interfaces (not just loopback) so the dev tool is reachable over Tailscale/LAN,
  // not only from this machine.
  fastify.listen({ port: PORT, host: '0.0.0.0' }, (err, address) => {
    if (err) {
      fastify.log.error(err);
      process.exit(1);
    }
    console.log(`Listening on ${address}`);
  });
}
