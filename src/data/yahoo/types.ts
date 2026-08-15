export interface AnalystPriceTarget {
  mean: number | null;
  high: number | null;
  low: number | null;
  numberOfAnalysts: number | null;
}

export interface AnalystConsensus {
  ticker: string;
  // Next-fiscal-year consensus EPS growth estimate, as a percent (e.g. 16.36 for 16.36%).
  // Yahoo no longer publishes a 5-year estimate on this endpoint (confirmed across multiple
  // tickers — see fetchAnalystConsensus's comment) so this is the longest-horizon growth
  // figure actually available, not a substitute for a 5y figure.
  nextYearEpsGrowthPercent: number | null;
  priceTarget: AnalystPriceTarget;
  // Yahoo's own consensus label, e.g. "strong_buy", "buy", "hold", "sell", "strong_sell".
  recommendationKey: string | null;
  asOf: string;
}

export type AnalystConsensusError =
  | { type: 'NOT_FOUND'; ticker: string }
  | { type: 'EMPTY_RESPONSE'; ticker: string }
  | { type: 'API_ERROR'; ticker: string; message: string };

export type AnalystConsensusResult =
  | { ok: true; data: AnalystConsensus }
  | { ok: false; error: AnalystConsensusError };
