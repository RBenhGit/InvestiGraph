// Orchestration layer — the single published entry point for src/data/yahoo. Nothing outside
// data/yahoo/ may import client.ts or types.ts directly.
//
// This is a second, independent data source alongside src/data/twelvedata/ — not a replacement
// and not a dependency of it. fetchStockData (twelvedata) already covers epsTtm/currentPrice/
// growth/historicalPe; this module only adds analyst price targets and next-year consensus EPS
// growth, which Twelve Data's growth_estimates endpoint (plan-gated to Ultra/Enterprise) can't
// supply on lower-tier keys. src/web/server.ts calls both in parallel and merges the results —
// this module failing must never take down a valuation that only needed twelvedata's data.

import { fetchQuoteSummary } from './client';
import type { AnalystConsensus, AnalystConsensusError, AnalystConsensusResult } from './types';

function toAnalystConsensusError(err: unknown, ticker: string): AnalystConsensusError {
  const message = err instanceof Error ? err.message : String(err);
  // yahoo-finance2 throws on an unknown symbol with a message that consistently mentions the
  // ticker was not found — same best-effort pattern as data/twelvedata/index.ts's NOT_FOUND
  // detection.
  if (/not found|no fundamentals|quote not found/i.test(message)) {
    return { type: 'NOT_FOUND', ticker };
  }
  return { type: 'API_ERROR', ticker, message };
}

export async function fetchAnalystConsensus(ticker: string): Promise<AnalystConsensusResult> {
  try {
    const result = await fetchQuoteSummary(ticker);

    if (!result.earningsTrend && !result.financialData) {
      return { ok: false, error: { type: 'EMPTY_RESPONSE', ticker } };
    }

    const nextYearTrend = result.earningsTrend?.trend?.find((entry) => entry.period === '+1y');
    const nextYearEpsGrowthPercent =
      typeof nextYearTrend?.growth === 'number' ? nextYearTrend.growth * 100 : null;

    const financialData = result.financialData;

    const data: AnalystConsensus = {
      ticker,
      nextYearEpsGrowthPercent,
      priceTarget: {
        mean: financialData?.targetMeanPrice ?? null,
        high: financialData?.targetHighPrice ?? null,
        low: financialData?.targetLowPrice ?? null,
        numberOfAnalysts: financialData?.numberOfAnalystOpinions ?? null,
      },
      recommendationKey: financialData?.recommendationKey ?? null,
      asOf: new Date().toISOString(),
    };

    return { ok: true, data };
  } catch (err) {
    return { ok: false, error: toAnalystConsensusError(err, ticker) };
  }
}
