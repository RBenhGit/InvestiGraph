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
  asOf: string;
}

export type AnalystConsensusError =
  | { type: 'NOT_FOUND'; ticker: string }
  | { type: 'EMPTY_RESPONSE'; ticker: string }
  | { type: 'API_ERROR'; ticker: string; message: string };

export type AnalystConsensusResult =
  | { ok: true; data: AnalystConsensus }
  | { ok: false; error: AnalystConsensusError };
