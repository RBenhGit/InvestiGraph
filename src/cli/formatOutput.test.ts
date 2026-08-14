import { describe, expect, it } from 'vitest';
import type { StockData } from '../data/twelvedata/types';
import { formatOutput } from './formatOutput';

const baseData: StockData = {
  ticker: 'AAPL',
  epsTtm: 6.42,
  currentPrice: 191.23,
  currency: 'USD',
  growth: {
    historical1yPercent: 12,
    historical3yPercent: null,
    historical5yPercent: null,
    analystEstimate5yPercent: 40,
  },
  historicalPe: { avg1y: 28.5, avg3y: null, avg5y: null },
  trailingPe: 29.79,
  providerReference: { trailingPe: 27.3, pegRatio: 2.1 },
  asOf: '2026-08-14T00:00:00.000Z',
};

describe('formatOutput', () => {
  it('shows both raw and clamped growth rate when the clamp fires', () => {
    const lynchResult = {
      ok: true as const,
      fairValue: 160.5,
      inputs: { epsTtm: 6.42, growthRatePercentRaw: 40, growthRatePercentClamped: 25 },
    };
    const ruleOneResult = {
      ok: true as const,
      fairValue: 210.1,
      inputs: {
        epsTtm: 6.42,
        growthRatePercentRaw: 40,
        growthRatePercentClamped: 25,
        exitPeMultiple: 15,
        requiredReturnPercent: 15,
        years: 10,
      },
      intermediate: { epsFuture: 20, futurePrice: 300 },
    };

    const output = formatOutput(baseData, lynchResult, ruleOneResult);

    expect(output).toContain('40');
    expect(output).toContain('25');
    expect(output).toContain('AAPL');
    expect(output).toContain('160.50');
    expect(output).toContain('210.10');
  });

  it('still shows the successful method when the other one failed', () => {
    const lynchResult = {
      ok: true as const,
      fairValue: 160.5,
      inputs: { epsTtm: 6.42, growthRatePercentRaw: 40, growthRatePercentClamped: 25 },
    };
    const ruleOneResult = { ok: false as const, error: 'INVALID_YEARS' as const };

    const output = formatOutput(baseData, lynchResult, ruleOneResult);

    expect(output).toContain('160.50');
    expect(output).toContain('FAILED (INVALID_YEARS)');
  });

  it('shows n/a for null historical P/E averages and providerReference fields', () => {
    const lynchResult = { ok: false as const, error: 'MISSING_GROWTH_RATE' as const };
    const ruleOneResult = { ok: false as const, error: 'MISSING_GROWTH_RATE' as const };

    const noGrowthData: StockData = {
      ...baseData,
      growth: {
        historical1yPercent: null,
        historical3yPercent: null,
        historical5yPercent: null,
        analystEstimate5yPercent: null,
      },
    };

    const output = formatOutput(noGrowthData, lynchResult, ruleOneResult);

    expect(output).toContain('n/a');
    expect(output).toContain('FAILED (MISSING_GROWTH_RATE)');
    expect(output).toContain('none available');
  });

  it('labels the growth source used', () => {
    const lynchResult = {
      ok: true as const,
      fairValue: 256.8,
      inputs: { epsTtm: 6.42, growthRatePercentRaw: 40, growthRatePercentClamped: 25 },
    };
    const ruleOneResult = {
      ok: true as const,
      fairValue: 300,
      inputs: {
        epsTtm: 6.42,
        growthRatePercentRaw: 40,
        growthRatePercentClamped: 25,
        exitPeMultiple: 15,
        requiredReturnPercent: 15,
        years: 10,
      },
    };

    const output = formatOutput(baseData, lynchResult, ruleOneResult);

    expect(output).toContain('analyst 5y estimate');
  });
});
