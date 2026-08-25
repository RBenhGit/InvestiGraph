import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fetchAnalystConsensus } from './index';
import { fetchQuoteSummary } from './client';
import { getCachedYahooData, saveCachedYahooData } from '../cache';

vi.mock('../cache', () => ({
  saveCachedYahooData: vi.fn(),
  getCachedYahooData: vi.fn().mockResolvedValue(null),
}));

vi.mock('./client', () => ({
  fetchQuoteSummary: vi.fn(),
}));

const TICKER = 'MSFT';

function quoteSummary(overrides: Record<string, unknown> = {}) {
  return {
    earningsTrend: {
      trend: [
        { period: '0q', growth: 0.1412 },
        { period: '+1q', growth: 0.1636 },
        { period: '0y', growth: 0.1403 },
        { period: '+1y', growth: 0.1953 },
      ],
    },
    financialData: {
      targetMeanPrice: 567.2,
      targetHighPrice: 870,
      targetLowPrice: 400,
      numberOfAnalystOpinions: 53,
      recommendationKey: 'strong_buy',
    },
    defaultKeyStatistics: {
      trailingEps: 11.03,
      mostRecentQuarter: '2026-06-30T00:00:00.000Z',
    },
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('fetchAnalystConsensus', () => {
  it('reads the +1y earnings-trend growth entry and financialData fields on success', async () => {
    vi.mocked(fetchQuoteSummary).mockResolvedValue(quoteSummary());

    const result = await fetchAnalystConsensus(TICKER);

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.data.ticker).toBe(TICKER);
    expect(result.data.nextYearEpsGrowthPercent).toBeCloseTo(19.53, 10);
    expect(result.data.priceTarget).toEqual({
      mean: 567.2,
      high: 870,
      low: 400,
      numberOfAnalysts: 53,
    });
    expect(result.data.recommendationKey).toBe('strong_buy');
    expect(result.data.trailingEps).toBe(11.03);
    expect(result.data.mostRecentQuarterEndDate).toBe('2026-06-30T00:00:00.000Z');
  });

  it('converts a Date-typed mostRecentQuarter to an ISO string', async () => {
    vi.mocked(fetchQuoteSummary).mockResolvedValue(
      quoteSummary({
        defaultKeyStatistics: {
          trailingEps: 8.72,
          mostRecentQuarter: new Date('2026-06-27T00:00:00.000Z'),
        },
      }),
    );

    const result = await fetchAnalystConsensus(TICKER);

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.data.trailingEps).toBe(8.72);
    expect(result.data.mostRecentQuarterEndDate).toBe('2026-06-27T00:00:00.000Z');
  });

  it('nulls trailingEps/mostRecentQuarterEndDate when defaultKeyStatistics is absent', async () => {
    vi.mocked(fetchQuoteSummary).mockResolvedValue(quoteSummary({ defaultKeyStatistics: undefined }));

    const result = await fetchAnalystConsensus(TICKER);

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.data.trailingEps).toBeNull();
    expect(result.data.mostRecentQuarterEndDate).toBeNull();
  });

  it('returns null growth when the +1y trend entry is absent (e.g. thin coverage)', async () => {
    vi.mocked(fetchQuoteSummary).mockResolvedValue(
      quoteSummary({ earningsTrend: { trend: [{ period: '0q', growth: 0.1 }] } }),
    );

    const result = await fetchAnalystConsensus(TICKER);

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.data.nextYearEpsGrowthPercent).toBeNull();
  });

  it('returns null price-target fields when financialData is absent', async () => {
    vi.mocked(fetchQuoteSummary).mockResolvedValue(
      quoteSummary({ financialData: undefined }),
    );

    const result = await fetchAnalystConsensus(TICKER);

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.data.priceTarget).toEqual({
      mean: null,
      high: null,
      low: null,
      numberOfAnalysts: null,
    });
    expect(result.data.recommendationKey).toBeNull();
  });

  it('reports EMPTY_RESPONSE when both modules are absent', async () => {
    vi.mocked(fetchQuoteSummary).mockResolvedValue({});

    const result = await fetchAnalystConsensus(TICKER);

    expect(result).toEqual({ ok: false, error: { type: 'EMPTY_RESPONSE', ticker: TICKER } });
  });

  it('infers NOT_FOUND when the thrown error signals an unknown symbol', async () => {
    vi.mocked(fetchQuoteSummary).mockRejectedValue(new Error('Quote not found for ticker symbol: NOTATICKER'));

    const result = await fetchAnalystConsensus(TICKER);

    expect(result).toEqual({ ok: false, error: { type: 'NOT_FOUND', ticker: TICKER } });
  });

  it('maps any other thrown error to API_ERROR', async () => {
    vi.mocked(fetchQuoteSummary).mockRejectedValue(new Error('network timeout'));

    const result = await fetchAnalystConsensus(TICKER);

    expect(result).toEqual({
      ok: false,
      error: { type: 'API_ERROR', ticker: TICKER, message: 'network timeout' },
    });
  });

  it('falls back to cached analyst data when fetch fails', async () => {
    vi.mocked(fetchQuoteSummary).mockRejectedValue(new Error('network down'));
    const mockCached = {
      ticker: TICKER,
      nextYearEpsGrowthPercent: 15,
      priceTarget: { mean: 500, high: 600, low: 400, numberOfAnalysts: 20 },
      recommendationKey: 'buy',
      beta: null,
      priceToSales: null,
      ruleOf40: null,
      trailingEps: 11.03,
      mostRecentQuarterEndDate: '2026-06-30T00:00:00.000Z',
      asOf: '2026-08-19T00:00:00.000Z',
    };
    vi.mocked(getCachedYahooData).mockResolvedValue(mockCached);

    const result = await fetchAnalystConsensus(TICKER);

    expect(result).toEqual({ ok: true, data: mockCached });
  });

  it('saves to cache on successful fetch', async () => {
    vi.mocked(fetchQuoteSummary).mockResolvedValue(quoteSummary());
    vi.mocked(getCachedYahooData).mockResolvedValue(null);

    const result = await fetchAnalystConsensus(TICKER);

    expect(result.ok).toBe(true);
    expect(saveCachedYahooData).toHaveBeenCalledWith(TICKER, expect.objectContaining({ ticker: TICKER }));
  });

  describe('beta, priceToSales, and ruleOf40', () => {
    it('reads beta and priceToSales straight from summaryDetail', async () => {
      vi.mocked(fetchQuoteSummary).mockResolvedValue(
        quoteSummary({ summaryDetail: { beta: 1.086, priceToSalesTrailing12Months: 9.649255 } }),
      );

      const result = await fetchAnalystConsensus(TICKER);

      expect(result.ok).toBe(true);
      if (!result.ok) return;
      expect(result.data.beta).toBe(1.086);
      expect(result.data.priceToSales).toBe(9.649255);
    });

    it('nulls beta and priceToSales when summaryDetail is absent', async () => {
      vi.mocked(fetchQuoteSummary).mockResolvedValue(quoteSummary({ summaryDetail: undefined }));

      const result = await fetchAnalystConsensus(TICKER);

      expect(result.ok).toBe(true);
      if (!result.ok) return;
      expect(result.data.beta).toBeNull();
      expect(result.data.priceToSales).toBeNull();
    });

    it('computes ruleOf40 as (revenueGrowth + ebitdaMargins) * 100 -- both fields are fractions, not percents', async () => {
      // Real NVDA-shaped figures: 85.2% revenue growth + 65.3% EBITDA margin = 150.5,
      // hand-verified live against Twelve Data/Yahoo before writing this expectation.
      vi.mocked(fetchQuoteSummary).mockResolvedValue(
        quoteSummary({
          financialData: { revenueGrowth: 0.852, ebitdaMargins: 0.65294 },
        }),
      );

      const result = await fetchAnalystConsensus(TICKER);

      expect(result.ok).toBe(true);
      if (!result.ok) return;
      expect(result.data.ruleOf40).toBeCloseTo(150.494, 10);
    });

    it('treats a genuine 0 for revenueGrowth or ebitdaMargins as a real value, not missing (falsy-zero regression guard)', async () => {
      // A flat-revenue, breakeven-EBITDA company: 0 + 0.4 = 40, not null.
      vi.mocked(fetchQuoteSummary).mockResolvedValue(
        quoteSummary({
          financialData: { revenueGrowth: 0, ebitdaMargins: 0.4 },
        }),
      );

      const result = await fetchAnalystConsensus(TICKER);

      expect(result.ok).toBe(true);
      if (!result.ok) return;
      expect(result.data.ruleOf40).toBeCloseTo(40, 10);
    });

    it('nulls ruleOf40 when revenueGrowth is missing', async () => {
      vi.mocked(fetchQuoteSummary).mockResolvedValue(
        quoteSummary({ financialData: { ebitdaMargins: 0.5 } }),
      );

      const result = await fetchAnalystConsensus(TICKER);

      expect(result.ok).toBe(true);
      if (!result.ok) return;
      expect(result.data.ruleOf40).toBeNull();
    });

    it('nulls ruleOf40 when ebitdaMargins is missing', async () => {
      vi.mocked(fetchQuoteSummary).mockResolvedValue(
        quoteSummary({ financialData: { revenueGrowth: 0.3 } }),
      );

      const result = await fetchAnalystConsensus(TICKER);

      expect(result.ok).toBe(true);
      if (!result.ok) return;
      expect(result.data.ruleOf40).toBeNull();
    });

    it('nulls ruleOf40 when financialData is absent entirely', async () => {
      vi.mocked(fetchQuoteSummary).mockResolvedValue(quoteSummary({ financialData: undefined }));

      const result = await fetchAnalystConsensus(TICKER);

      expect(result.ok).toBe(true);
      if (!result.ok) return;
      expect(result.data.ruleOf40).toBeNull();
    });
  });
});
