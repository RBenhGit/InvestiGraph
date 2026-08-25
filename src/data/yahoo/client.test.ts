import { describe, it, expect, vi } from 'vitest';
import { fetchQuoteSummary } from './client';
import YahooFinance from 'yahoo-finance2';

// Mock the yahooFinance default export
vi.mock('yahoo-finance2', () => {
  const quoteSummary = vi.fn();
  const mockClass = class {
    quoteSummary = quoteSummary;
  };
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (mockClass as any).quoteSummary = quoteSummary; // attach for easy access in tests
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
