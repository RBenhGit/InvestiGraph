// Orchestration layer — the single published entry point for src/data/yahoo. Nothing outside
// data/yahoo/ may import client.ts or types.ts directly.
//
// This is a second, independent data source alongside src/data/twelvedata/ — not a replacement
// and not a dependency of it. fetchStockData (twelvedata) already covers epsTtm/currentPrice/
// growth/historicalPe; this module only adds analyst price targets and next-year consensus EPS
// growth, which Twelve Data's growth_estimates endpoint (plan-gated to Ultra/Enterprise) can't
// supply on lower-tier keys. src/web/server.ts calls both in parallel and merges the results —
// this module failing must never take down a valuation that only needed twelvedata's data.

import { fetchQuoteSummary, fetchAnnualRevenueSeries } from './client';
import type { AnnualFinancialsPoint } from './client';
import { saveCachedYahooData, getCachedYahooData } from '../cache';
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

// Derives a single YoY revenue growth fraction from the two most recent annual points, to
// period-match ebitdaMargins (a TTM figure from quoteSummary's financialData) inside ruleOf40.
// financialData.revenueGrowth is Yahoo's quarterly YoY figure, not annual -- live-confirmed to
// diverge sharply from the true annual figure for accelerating companies (e.g. NVDA reports
// 85.2% quarterly vs. 65.47% actual annual growth), which previously inflated ruleOf40. Returns
// null when fewer than 2 valid points are available -- deliberately no fallback to the
// mismatched quarterly figure, since that's the exact bug being fixed.
function deriveAnnualRevenueGrowth(points: AnnualFinancialsPoint[]): number | null {
  const valid = points
    .filter(
      (p): p is AnnualFinancialsPoint & { operatingRevenue: number } =>
        typeof p.operatingRevenue === 'number' && Number.isFinite(p.operatingRevenue),
    )
    .map((p) => ({ date: new Date(p.date), revenue: p.operatingRevenue }))
    .filter((p) => !Number.isNaN(p.date.getTime()))
    .sort((a, b) => a.date.getTime() - b.date.getTime());

  if (valid.length < 2) return null;

  const [previous, latest] = valid.slice(-2);
  if (previous.revenue === 0) return null;

  return latest.revenue / previous.revenue - 1;
}

export interface FetchAnalystOptions {
  forceRefresh?: boolean;
  maxAgeMs?: number;
}

const DEFAULT_YAHOO_CACHE_TTL_MS = 24 * 60 * 60 * 1000; // 24 hours

export async function fetchAnalystConsensus(
  ticker: string,
  options?: FetchAnalystOptions,
): Promise<AnalystConsensusResult> {
  const normalizedTicker = ticker.toUpperCase();

  if (!options?.forceRefresh) {
    const cached = await getCachedYahooData(normalizedTicker);
    if (cached) {
      const age = Date.now() - new Date(cached.asOf).getTime();
      const maxAge = options?.maxAgeMs ?? DEFAULT_YAHOO_CACHE_TTL_MS;
      if (Number.isFinite(age) && age < maxAge) {
        return { ok: true, data: cached };
      }
    }
  }

  try {
    const [result, annualRevenueSeries] = await Promise.all([
      fetchQuoteSummary(ticker),
      // Auxiliary to an auxiliary: this module already degrades gracefully to null if it fails
      // entirely (see the module comment at the top of this file), and ruleOf40 is reference-
      // only within it -- a failure here must not take down the rest of the consensus data.
      fetchAnnualRevenueSeries(ticker).catch(() => []),
    ]);

    if (!result.earningsTrend && !result.financialData) {
      return { ok: false, error: { type: 'EMPTY_RESPONSE', ticker } };
    }

    const nextYearTrend = result.earningsTrend?.trend?.find((entry) => entry.period === '+1y');
    const nextYearEpsGrowthPercent =
      typeof nextYearTrend?.growth === 'number' ? nextYearTrend.growth * 100 : null;

    const financialData = result.financialData;
    const summaryDetail = result.summaryDetail;

    // Yahoo reports ebitdaMargins as a literal 0 both when a company is genuinely breakeven on
    // EBITDA AND when it has no EBITDA figure to compute a margin from at all (confirmed live:
    // MS/JPM/BAC -- banks, where EBITDA isn't a tracked concept -- all return
    // `ebitda: undefined, ebitdaMargins: 0`), or when the underlying ebitda is negative
    // (confirmed live: IONQ has `ebitda: -793,051,008` on ~246M revenue -- a true margin of
    // about -322% -- yet still reports `ebitdaMargins: 0`). Treating that 0 as a real value
    // previously fabricated a Rule of 40 score from revenueGrowth alone (MS: 28, tagged
    // "warning") or produced the exact opposite of the truth (IONQ: 286.80, tagged "good" for a
    // company burning 3x its revenue). A margin of exactly 0 is only trustworthy when the raw
    // ebitda figure is actually present and non-negative -- a real negative ebitda can never
    // round to a margin of exactly 0.
    const ebitda = financialData?.ebitda;
    const ebitdaMarginIsTrustworthy =
      financialData?.ebitdaMargins !== 0 || (ebitda !== undefined && ebitda !== null && ebitda >= 0);

    // Growth numerator is annual (see deriveAnnualRevenueGrowth), not financialData.revenueGrowth
    // (quarterly YoY) -- period-matched against ebitdaMargins, which is TTM.
    const annualRevenueGrowth = deriveAnnualRevenueGrowth(annualRevenueSeries);

    let ruleOf40 = null;
    if (
      annualRevenueGrowth !== null &&
      financialData?.ebitdaMargins !== undefined &&
      financialData.ebitdaMargins !== null &&
      ebitdaMarginIsTrustworthy
    ) {
      ruleOf40 = (annualRevenueGrowth + financialData.ebitdaMargins) * 100;
    }

    const defaultKeyStatistics = result.defaultKeyStatistics;
    const rawMostRecentQuarter = defaultKeyStatistics?.mostRecentQuarter;
    const mostRecentQuarterEndDate =
      rawMostRecentQuarter instanceof Date
        ? rawMostRecentQuarter.toISOString()
        : typeof rawMostRecentQuarter === 'string'
          ? rawMostRecentQuarter
          : null;

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
      beta: summaryDetail?.beta ?? null,
      priceToSales: summaryDetail?.priceToSalesTrailing12Months ?? null,
      ruleOf40,
      trailingEps: defaultKeyStatistics?.trailingEps ?? null,
      mostRecentQuarterEndDate,
      asOf: new Date().toISOString(),
    };

    await saveCachedYahooData(ticker, data);

    return { ok: true, data };
  } catch (err) {
    const cached = await getCachedYahooData(ticker);
    if (cached) {
      return { ok: true, data: cached };
    }
    return { ok: false, error: toAnalystConsensusError(err, ticker) };
  }
}
