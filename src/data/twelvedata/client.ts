// Raw HTTP calls against the Twelve Data REST API. No response assembly here — that's
// index.ts's job (task 5). Every function fetches one endpoint, checks the HTTP status,
// validates the parsed body with `assertNonEmpty`, and returns the typed JSON body as-is
// (still carrying string-typed numeric fields where Twelve Data sends them that way —
// callers use `parseNumber` from normalize.ts to convert).

import { assertNonEmpty, TwelveDataResponseError } from './normalize';

const BASE_URL = 'https://api.twelvedata.com';

export interface QuoteResponse {
  symbol: string;
  currency: string;
  close: string;
}

export interface StatisticsResponse {
  statistics: {
    valuations_metrics: {
      trailing_pe?: number;
      peg_ratio?: number;
    };
  };
}

export interface GrowthEstimatesResponse {
  growth_estimates: {
    past_5_years_pa?: number;
    next_5_years_pa?: number;
  };
}

export interface IncomeStatementEntry {
  fiscal_date: string;
  eps_diluted: unknown;
  diluted_shares_outstanding: unknown;
}

export interface IncomeStatementResponse {
  income_statement: IncomeStatementEntry[];
}

export interface TimeSeriesEntry {
  datetime: string;
  close: string;
}

export interface TimeSeriesResponse {
  // `meta.currency` is present on live `time_series` responses (confirmed during task 4's
  // live-call verification) but wasn't needed by client.ts itself — index.ts uses it as the
  // fundamentals-side currency to cross-check against `quote.currency`.
  meta?: { currency?: string };
  values: TimeSeriesEntry[];
}

/**
 * Fetches one Twelve Data endpoint and validates the body.
 *
 * A non-2xx HTTP status is folded into the same `TwelveDataResponseError('API_ERROR', ...)`
 * path that a `status: "error"` body produces (rather than parsing a possibly-non-JSON body
 * on failure) — one error type for callers to handle, one consistent rule: only a 2xx response
 * is ever inspected for a `status: "error"` payload or emptiness.
 */
async function twelveDataFetch<T>(url: string, endpoint: string): Promise<T> {
  const response = await fetch(url);

  if (!response.ok) {
    if (response.status === 429) {
      throw new TwelveDataResponseError('RATE_LIMIT', endpoint);
    }
    throw new TwelveDataResponseError(
      'API_ERROR',
      endpoint,
      `HTTP ${response.status} ${response.statusText}`,
    );
  }

  const body: unknown = await response.json();
  assertNonEmpty(body, endpoint);
  return body as T;
}

export async function fetchQuote(ticker: string, apiKey: string): Promise<QuoteResponse> {
  const url = `${BASE_URL}/quote?symbol=${encodeURIComponent(ticker)}&apikey=${apiKey}`;
  return twelveDataFetch<QuoteResponse>(url, 'quote');
}

export async function fetchStatistics(ticker: string, apiKey: string): Promise<StatisticsResponse> {
  const url = `${BASE_URL}/statistics?symbol=${encodeURIComponent(ticker)}&apikey=${apiKey}`;
  return twelveDataFetch<StatisticsResponse>(url, 'statistics');
}

export async function fetchGrowthEstimates(
  ticker: string,
  apiKey: string,
): Promise<GrowthEstimatesResponse> {
  const url = `${BASE_URL}/growth_estimates?symbol=${encodeURIComponent(ticker)}&apikey=${apiKey}`;
  return twelveDataFetch<GrowthEstimatesResponse>(url, 'growth_estimates');
}

/** Quarterly income statement, outputsize=6 — the hard ceiling on this plan tier (HTTP 400,
 * "Full access to historical data is available only in the Enterprise plan" above 6).
 * `resolveTtmEps`/epsTtm only needs 4, but `calculateTtmEpsGrowthPercent` (normalize.ts) wants
 * a true year-over-year TTM comparison, which needs 8 — 6 is as close as this plan tier gets, so
 * that function correctly returns `null` (not a misleading shorter-window approximation) until
 * the plan is upgraded past this cap. `historicalPe` (see historicalPe.ts) computes its P/E
 * windows from *annual* EPS instead of quarterly, which isn't subject to this cap (see
 * fetchAnnualIncomeStatement below). */
export async function fetchQuarterlyIncomeStatement(
  ticker: string,
  apiKey: string,
): Promise<IncomeStatementResponse> {
  const url = `${BASE_URL}/income_statement?symbol=${encodeURIComponent(ticker)}&period=quarterly&outputsize=6&apikey=${apiKey}`;
  return twelveDataFetch<IncomeStatementResponse>(url, 'income_statement (quarterly)');
}

/** Annual income statement, outputsize=6 (confirmed live: the max this plan tier allows before
 * the same Enterprise-only 400 as the quarterly endpoint above), for the 1y/3y/5y historical
 * CAGR calculations and the annual-EPS P/E-average windows in historicalPe.ts. 6 entries is
 * exactly enough for a 5y CAGR (index 0 vs. index 5) and a 5-point trailing P/E-average window. */
export async function fetchAnnualIncomeStatement(
  ticker: string,
  apiKey: string,
): Promise<IncomeStatementResponse> {
  const url = `${BASE_URL}/income_statement?symbol=${encodeURIComponent(ticker)}&period=annual&outputsize=6&apikey=${apiKey}`;
  return twelveDataFetch<IncomeStatementResponse>(url, 'income_statement (annual)');
}

export async function fetchMonthlyTimeSeries(
  ticker: string,
  apiKey: string,
): Promise<TimeSeriesResponse> {
  const url = `${BASE_URL}/time_series?symbol=${encodeURIComponent(ticker)}&interval=1month&outputsize=61&apikey=${apiKey}`;
  return twelveDataFetch<TimeSeriesResponse>(url, 'time_series');
}
