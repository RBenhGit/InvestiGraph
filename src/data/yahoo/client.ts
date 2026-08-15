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
  };
}

/**
 * Fetches `earningsTrend` + `financialData` for one ticker via yahoo-finance2's undocumented
 * `quoteSummary` endpoint (the same public endpoint yahoo-finance.com's own UI calls — no API
 * key, no official SLA). Confirmed live across MSFT/AAPL/TSLA: Yahoo no longer returns a "+5y"
 * long-term-growth entry in `earningsTrend.trend` (it's been dropped from the public feed) —
 * only "0q"/"+1q"/"0y"/"+1y" are present, so index.ts reads "+1y" as the longest-horizon
 * consensus growth figure actually available, not a 5-year estimate.
 */
export async function fetchQuoteSummary(ticker: string): Promise<QuoteSummaryResult> {
  return yahooFinance.quoteSummary(ticker, {
    modules: ['earningsTrend', 'financialData'],
  }) as Promise<QuoteSummaryResult>;
}
