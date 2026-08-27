import { describe, it, expect, vi } from 'vitest';
import { fetchQuoteSummary, fetchAnnualRevenueSeries } from './client';
import YahooFinance from 'yahoo-finance2';

// Mock the yahooFinance default export
vi.mock('yahoo-finance2', () => {
  const quoteSummary = vi.fn();
  const fundamentalsTimeSeries = vi.fn();
  const mockClass = class {
    quoteSummary = quoteSummary;
    fundamentalsTimeSeries = fundamentalsTimeSeries;
  };
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (mockClass as any).quoteSummary = quoteSummary; // attach for easy access in tests
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (mockClass as any).fundamentalsTimeSeries = fundamentalsTimeSeries;
  return { default: mockClass };
});

describe('yahoo client', () => {
  it('calls yahooFinance.quoteSummary with correct arguments', async () => {
    const mockResult = {
      earningsTrend: { trend: [{ period: '+1y', growth: 0.15 }] },
      financialData: { recommendationKey: 'buy' },
      summaryDetail: { beta: 1.2, priceToSalesTrailing12Months: 5.4 },
    };
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const quoteSummaryMock = (YahooFinance as any).quoteSummary;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (quoteSummaryMock as any).mockResolvedValue(mockResult);

    const result = await fetchQuoteSummary('AAPL');

    expect(quoteSummaryMock).toHaveBeenCalledWith('AAPL', {
      modules: ['earningsTrend', 'financialData', 'summaryDetail', 'defaultKeyStatistics'],
    });
    expect(result).toEqual(mockResult);
  });
});

describe('fetchAnnualRevenueSeries', () => {
  it('calls yahooFinance.fundamentalsTimeSeries with annual/financials and returns the raw points', async () => {
    const mockPoints = [
      { date: new Date('2024-12-31'), operatingRevenue: 7_003_000_000 },
      { date: new Date('2025-12-31'), operatingRevenue: 9_012_000_000 },
    ];
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const fundamentalsTimeSeriesMock = (YahooFinance as any).fundamentalsTimeSeries;
    fundamentalsTimeSeriesMock.mockResolvedValue(mockPoints);

    const result = await fetchAnnualRevenueSeries('ANET');

    expect(fundamentalsTimeSeriesMock).toHaveBeenCalledWith('ANET', {
      period1: '2015-01-01',
      type: 'annual',
      module: 'financials',
    });
    expect(result).toEqual(mockPoints);
  });

  it('returns an empty array instead of throwing when the underlying call resolves to a non-array (e.g. an unknown ticker)', async () => {
    // yahoo-finance2 confirmed live to resolve an unknown ticker to [] rather than throwing --
    // this guard is defense-in-depth against any other non-array shape.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const fundamentalsTimeSeriesMock = (YahooFinance as any).fundamentalsTimeSeries;
    fundamentalsTimeSeriesMock.mockResolvedValue(undefined);

    const result = await fetchAnnualRevenueSeries('ZZZZZNOPE');

    expect(result).toEqual([]);
  });
});
