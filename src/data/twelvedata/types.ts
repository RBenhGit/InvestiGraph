export interface HistoricalPeAverages {
  avg1y: number | null;
  avg3y: number | null;
  avg5y: number | null;
}

export interface QuarterlyEpsPoint {
  periodEnd: string;
  dilutedEps: number;
}

export interface MonthlyClosePoint {
  date: string;
  close: number;
}

export interface StockData {
  ticker: string;
  epsTtm: number;
  currentPrice: number;
  currency: string;
  // All growth figures below are raw, unclamped — clamping happens in valuation/.
  // Each is independently nullable: a ticker can have thin annual history (young IPO)
  // or no analyst coverage without failing the whole lookup.
  growth: {
    historical1yPercent: number | null; // computed locally: EPS(latest annual) / EPS(1y ago) − 1
    historical3yPercent: number | null; // computed locally: CAGR over 3 annual periods
    historical5yPercent: number | null; // passthrough: growth_estimates.past_5_years_pa × 100
    analystEstimate5yPercent: number | null; // passthrough: growth_estimates.next_5_years_pa × 100 — real consensus, verified live
  };
  historicalPe: HistoricalPeAverages;
  trailingPe: number | null; // recomputed locally as price/eps, never trusted from the API field
  // Provider's own statistics.valuations_metrics figures — reference only, never fed into
  // Method A/B or into `trailingPe` above (see that field's comment).
  providerReference: {
    trailingPe: number | null;
    pegRatio: number | null;
  };
  asOf: string;
}

export type StockDataError =
  | { type: 'NOT_FOUND'; ticker: string }
  | { type: 'INSUFFICIENT_DATA'; ticker: string; reason: string }
  | { type: 'EMPTY_RESPONSE'; ticker: string; endpoint: string }
  | { type: 'API_ERROR'; ticker: string; endpoint: string; message: string }
  | { type: 'INVALID_CURRENCY_UNIT'; ticker: string; detail: string };

export type StockDataResult = { ok: true; data: StockData } | { ok: false; error: StockDataError };
