export interface AnalystPriceTarget {
  mean: number | null;
  high: number | null;
  low: number | null;
  numberOfAnalysts: number | null;
}

export interface AnalystConsensus {
  ticker: string;
  nextYearEpsGrowthPercent: number | null;
  priceTarget: AnalystPriceTarget;
  recommendationKey: string | null;
  beta: number | null;
  priceToSales: number | null;
  ruleOf40: number | null;
  // GAAP trailing EPS from Yahoo's defaultKeyStatistics — an independent cross-check/fallback
  // source for StockData.epsTtm, used by resolveEpsWithFallback when Twelve Data's epsTtm looks
  // stale (see StockData.staleTtmWarning). mostRecentQuarterEndDate is Yahoo's own freshness
  // signal for trailingEps, surfaced so a fallback can be labeled with which quarter it reflects.
  trailingEps: number | null;
  mostRecentQuarterEndDate: string | null;
  asOf: string;
}

export type AnalystConsensusError =
  | { type: 'NOT_FOUND'; ticker: string }
  | { type: 'EMPTY_RESPONSE'; ticker: string }
  | { type: 'API_ERROR'; ticker: string; message: string };

export type AnalystConsensusResult =
  | { ok: true; data: AnalystConsensus }
  | { ok: false; error: AnalystConsensusError };
