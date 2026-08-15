// Orchestration layer — the single published entry point for src/data/twelvedata. Wires
// client.ts's raw HTTP calls through normalize.ts/historicalPe.ts into one StockDataResult.
// Nothing outside data/twelvedata/ may import any other file in this directory.

import { loadTwelveDataApiKey } from './env';
import {
  fetchAnnualIncomeStatement,
  fetchGrowthEstimates,
  fetchMonthlyTimeSeries,
  fetchQuarterlyIncomeStatement,
  fetchQuote,
  fetchStatistics,
  type IncomeStatementEntry,
} from './client';
import {
  calculateCagrPercent,
  CurrencyMismatchError,
  parseNumber,
  resolveTtmEps,
  TwelveDataResponseError,
  validateCurrency,
} from './normalize';
import { computeHistoricalPeAverages } from './historicalPe';
import type {
  MonthlyClosePoint,
  QuarterlyEpsPoint,
  StockData,
  StockDataError,
  StockDataResult,
} from './types';

/** Converts a decimal `growth_estimates` field (e.g. `0.0866`) to a percent, or `null` if the
 * field is missing/unparseable. */
function toPercent(value: unknown): number | null {
  const parsed = parseNumber(value);
  return parsed === null ? null : parsed * 100;
}

/** Parses one income-statement entry's diluted EPS, or `null` if missing/unparseable. */
function parsedEps(entry: IncomeStatementEntry): number | null {
  return parseNumber(entry.eps_diluted);
}

/** Maps a thrown error from the fetch/normalize layer onto a `StockDataError` variant. */
function toStockDataError(err: unknown, ticker: string): StockDataError {
  if (err instanceof CurrencyMismatchError) {
    return { type: 'INVALID_CURRENCY_UNIT', ticker, detail: err.detail };
  }
  if (err instanceof TwelveDataResponseError) {
    if (err.type === 'EMPTY_RESPONSE') {
      return { type: 'EMPTY_RESPONSE', ticker, endpoint: err.endpoint };
    }
    const message = err.apiMessage ?? err.message;
    // Cheap, best-effort signal for a clearly-unknown ticker — Twelve Data's own error
    // messages for a bad symbol consistently mention "not found"/"no data"/"invalid symbol".
    if (/not found|no data|invalid symbol/i.test(message)) {
      return { type: 'NOT_FOUND', ticker };
    }
    return { type: 'API_ERROR', ticker, endpoint: err.endpoint, message };
  }
  const message = err instanceof Error ? err.message : String(err);
  return { type: 'API_ERROR', ticker, endpoint: 'unknown', message };
}

export async function fetchStockData(ticker: string): Promise<StockDataResult> {
  try {
    const apiKey = loadTwelveDataApiKey();

    const [quote, statistics, quarterlyIncome, annualIncome, monthlyTimeSeries] = await Promise.all(
      [
        fetchQuote(ticker, apiKey),
        fetchStatistics(ticker, apiKey),
        fetchQuarterlyIncomeStatement(ticker, apiKey),
        fetchAnnualIncomeStatement(ticker, apiKey),
        fetchMonthlyTimeSeries(ticker, apiKey),
      ],
    );

    // growth_estimates is gated behind Twelve Data's higher plan tiers (confirmed live: a
    // non-ultra/enterprise key gets a 403 here while every other endpoint succeeds) — this
    // must not fail the whole lookup. historical5y/analystEstimate5y simply stay null, same as
    // any other "no analyst coverage" case StockData.growth already treats as independently
    // nullable (1y/3y CAGR and historicalPe still come from data this key does have access to).
    const growthEstimates = await fetchGrowthEstimates(ticker, apiKey).catch(() => null);

    const fundamentalsCurrency = monthlyTimeSeries.meta?.currency;
    if (fundamentalsCurrency) {
      validateCurrency(quote.currency, fundamentalsCurrency);
    }

    const quarterlyEntries = quarterlyIncome.income_statement;

    // Only full quarters (both EPS and shares parse cleanly) feed the TTM fallback — a quarter
    // missing either figure can't contribute a trustworthy net-income term.
    const quarterlyDilutedEpsAll: number[] = [];
    const quarterlyDilutedSharesAll: number[] = [];
    for (const entry of quarterlyEntries) {
      const eps = parsedEps(entry);
      const shares = parseNumber(entry.diluted_shares_outstanding);
      if (eps === null || shares === null) continue;
      quarterlyDilutedEpsAll.push(eps);
      quarterlyDilutedSharesAll.push(shares);
    }

    // statistics.valuations_metrics has no point-in-time EPS field (only trailing_pe/peg_ratio,
    // used below as reference-only figures), so the quarterly-derived TTM is authoritative.
    const epsTtm = resolveTtmEps(null, quarterlyDilutedEpsAll, quarterlyDilutedSharesAll);

    if (epsTtm === null) {
      return {
        ok: false,
        error: { type: 'INSUFFICIENT_DATA', ticker, reason: 'unable to resolve TTM EPS' },
      };
    }

    const currentPrice = parseNumber(quote.close);
    if (currentPrice === null) {
      return {
        ok: false,
        error: { type: 'INSUFFICIENT_DATA', ticker, reason: 'unable to parse current price' },
      };
    }

    const annualEps = annualIncome.income_statement.map(parsedEps);
    const historical1yPercent =
      annualEps.length >= 2 ? calculateCagrPercent(annualEps[0], annualEps[1], 1) : null;
    const historical3yPercent =
      annualEps.length >= 4 ? calculateCagrPercent(annualEps[0], annualEps[3], 3) : null;

    const historical5yPercent = toPercent(growthEstimates?.growth_estimates.past_5_years_pa);
    const analystEstimate5yPercent = toPercent(growthEstimates?.growth_estimates.next_5_years_pa);

    const quarterlyEpsPoints: QuarterlyEpsPoint[] = quarterlyEntries
      .map((entry) => ({ periodEnd: entry.fiscal_date, dilutedEps: parsedEps(entry) }))
      .filter((point): point is QuarterlyEpsPoint => point.dilutedEps !== null);

    const monthlyClosePoints: MonthlyClosePoint[] = monthlyTimeSeries.values
      .map((value) => ({ date: value.datetime, close: parseNumber(value.close) }))
      .filter((point): point is MonthlyClosePoint => point.close !== null);

    const historicalPe = computeHistoricalPeAverages(quarterlyEpsPoints, monthlyClosePoints);

    const trailingPe = epsTtm > 0 ? currentPrice / epsTtm : null;

    const data: StockData = {
      ticker,
      epsTtm,
      currentPrice,
      currency: quote.currency,
      growth: {
        historical1yPercent,
        historical3yPercent,
        historical5yPercent,
        analystEstimate5yPercent,
      },
      historicalPe,
      trailingPe,
      providerReference: {
        trailingPe: parseNumber(statistics.statistics.valuations_metrics.trailing_pe),
        pegRatio: parseNumber(statistics.statistics.valuations_metrics.peg_ratio),
      },
      asOf: new Date().toISOString(),
    };

    return { ok: true, data };
  } catch (err) {
    return { ok: false, error: toStockDataError(err, ticker) };
  }
}
