import { describe, expect, it } from 'vitest';
import { resolveEpsWithFallback } from './resolveEps';
import type { StockData } from './twelvedata/types';
import type { AnalystConsensus } from './yahoo/types';

const TICKER = 'CSCO';

function stockData(overrides: Partial<StockData> = {}): StockData {
  return {
    ticker: TICKER,
    epsTtm: 3.08,
    currentPrice: 110.23,
    currency: 'USD',
    growth: {
      historical1yPercent: null,
      historical3yPercent: null,
      historical5yPercent: null,
      analystEstimate5yPercent: null,
    },
    historicalPe: { avg1y: null, avg3y: null, avg5y: null },
    trailingPe: 35.79,
    providerReference: { trailingPe: 33.35, pegRatio: null },
    staleTtmWarning: false,
    asOf: '2026-08-25T00:00:00.000Z',
    ...overrides,
  };
}

function analystConsensus(overrides: Partial<AnalystConsensus> = {}): AnalystConsensus {
  return {
    ticker: TICKER,
    nextYearEpsGrowthPercent: null,
    priceTarget: { mean: null, high: null, low: null, numberOfAnalysts: null },
    recommendationKey: null,
    beta: null,
    priceToSales: null,
    ruleOf40: null,
    trailingEps: 3.31,
    mostRecentQuarterEndDate: '2026-07-25T00:00:00.000Z',
    asOf: '2026-08-25T07:00:00.000Z',
    ...overrides,
  };
}

describe('resolveEpsWithFallback', () => {
  it('uses Twelve Data as-is when staleTtmWarning is false, regardless of Yahoo data', () => {
    const result = resolveEpsWithFallback(
      stockData({ staleTtmWarning: false }),
      analystConsensus(),
    );

    expect(result.epsTtm).toBe(3.08);
    expect(result.source).toBe('twelvedata');
  });

  it('falls back to Yahoo trailingEps when staleTtmWarning is true and Yahoo has a positive figure', () => {
    const result = resolveEpsWithFallback(
      stockData({ staleTtmWarning: true }),
      analystConsensus({ trailingEps: 3.31 }),
    );

    expect(result.epsTtm).toBe(3.31);
    expect(result.source).toBe('yahoo-fallback');
    expect(result.detail).toContain('Yahoo Finance');
    expect(result.detail).toContain('3.08'); // names the superseded Twelve Data figure
  });

  it('keeps the stale Twelve Data figure when analystConsensus is null (Yahoo call failed)', () => {
    const result = resolveEpsWithFallback(stockData({ staleTtmWarning: true }), null);

    expect(result.epsTtm).toBe(3.08);
    expect(result.source).toBe('twelvedata-stale-no-fallback');
    expect(result.detail).toContain('unavailable');
  });

  it('keeps the stale Twelve Data figure when Yahoo trailingEps is null', () => {
    const result = resolveEpsWithFallback(
      stockData({ staleTtmWarning: true }),
      analystConsensus({ trailingEps: null }),
    );

    expect(result.epsTtm).toBe(3.08);
    expect(result.source).toBe('twelvedata-stale-no-fallback');
  });

  it('keeps the stale Twelve Data figure when Yahoo trailingEps is zero or negative', () => {
    const zeroResult = resolveEpsWithFallback(
      stockData({ staleTtmWarning: true }),
      analystConsensus({ trailingEps: 0 }),
    );
    const negativeResult = resolveEpsWithFallback(
      stockData({ staleTtmWarning: true }),
      analystConsensus({ trailingEps: -1.2 }),
    );

    expect(zeroResult.source).toBe('twelvedata-stale-no-fallback');
    expect(negativeResult.source).toBe('twelvedata-stale-no-fallback');
  });
});
