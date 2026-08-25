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
