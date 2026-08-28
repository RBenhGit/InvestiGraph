// Raw call against yahoo-finance2's quoteSummary. No response assembly here — that's
// index.ts's job, same split as data/twelvedata/{client,index}.ts.

import YahooFinance from 'yahoo-finance2';

const yahooFinance = new YahooFinance({ suppressNotices: ['yahooSurvey'] });

export interface EarningsTrendEntry {
  period: string; // e.g. "0q", "+1q", "0y", "+1y" — see fetchQuoteSummary's comment on why
  // there is no "+5y" entry to read here.
  growth: number | null | undefined;
}

export interface QuoteSummaryResult {
  earningsTrend?: { trend?: EarningsTrendEntry[] };
  financialData?: {
    targetMeanPrice?: number | null;
    targetHighPrice?: number | null;
    targetLowPrice?: number | null;
    numberOfAnalystOpinions?: number | null;
    recommendationKey?: string | null;
    revenueGrowth?: number | null;
    ebitdaMargins?: number | null;
    // Raw EBITDA, read only to disambiguate ebitdaMargins -- Yahoo reports a literal 0 for
    // ebitdaMargins both when it's genuinely breakeven AND when it has no EBITDA figure to
    // compute a margin from at all (e.g. banks) or when the underlying ebitda is negative (see
    // index.ts's ruleOf40 guard). Not otherwise surfaced.
    ebitda?: number | null;
  };
  summaryDetail?: {
    beta?: number | null;
    priceToSalesTrailing12Months?: number | null;
  };
  // GAAP trailing-twelve-month diluted EPS, confirmed live against CSCO to match Yahoo's own
  // `mostRecentQuarter` timestamp (i.e. this field itself rolls forward promptly after a real
  // earnings release, unlike Twelve Data's quarterly income_statement — see
  // detectStaleTtmEps/resolveEpsWithFallback). No per-quarter breakdown is available on this
  // module — trailingEps is already a summed TTM figure, not decomposable back into quarters.
  defaultKeyStatistics?: {
    trailingEps?: number | null;
    mostRecentQuarter?: string | Date | null;
  };
}

export async function fetchQuoteSummary(ticker: string): Promise<QuoteSummaryResult> {
  return yahooFinance.quoteSummary(ticker, {
    modules: ['earningsTrend', 'financialData', 'summaryDetail', 'defaultKeyStatistics'],
  }) as Promise<QuoteSummaryResult>;
}

export interface AnnualFinancialsPoint {
  date: string | Date;
  operatingRevenue?: number | null;
}

// Raw annual revenue points, period-matched to ebitdaMargins (which quoteSummary's
// financialData reports as a TTM figure) -- quoteSummary's own financialData.revenueGrowth is
// quarterly YoY, not annual, and mixing the two periods in ruleOf40 systematically inflates the
// score for accelerating companies (see index.ts's ruleOf40 annual-growth derivation). A
// separate call, since quoteSummary has no annual-period revenue series of its own; confirmed
// live to return one point per fiscal year (12M periodType) with `operatingRevenue`, oldest
// first once sorted -- an unknown ticker resolves to an empty array rather than throwing.
export async function fetchAnnualRevenueSeries(ticker: string): Promise<AnnualFinancialsPoint[]> {
  const result = (await yahooFinance.fundamentalsTimeSeries(ticker, {
    period1: '2015-01-01',
    type: 'annual',
    module: 'financials',
  })) as AnnualFinancialsPoint[];
  return Array.isArray(result) ? result : [];
}
