import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fetchAnalystConsensus } from './index';
import { fetchQuoteSummary, fetchAnnualRevenueSeries } from './client';
import { getCachedYahooData, saveCachedYahooData } from '../cache';

vi.mock('../cache', () => ({
  saveCachedYahooData: vi.fn(),
  getCachedYahooData: vi.fn().mockResolvedValue(null),
}));

vi.mock('./client', () => ({
  fetchQuoteSummary: vi.fn(),
  fetchAnnualRevenueSeries: vi.fn().mockResolvedValue([]),
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
  // vi.clearAllMocks() resets call history but NOT a mock's resolved/rejected implementation --
  // without this, an earlier test's fetchAnnualRevenueSeries fixture silently bleeds into any
  // later test that doesn't set its own (confirmed live: broke 'nulls ruleOf40 when
  // revenueGrowth is missing' when the ruleOf40 period-mismatch tests were added).
  vi.mocked(fetchAnnualRevenueSeries).mockResolvedValue([]);
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

    it('computes ruleOf40 as (annual revenue growth + ebitdaMargins) * 100 -- growth comes from fetchAnnualRevenueSeries, not the quarterly financialData.revenueGrowth (see period-mismatch fix below)', async () => {
      // Real NVDA-shaped figures: annual revenue 130.50B -> 215.94B (65.47% YoY) + 65.3% TTM
      // EBITDA margin, hand-verified live against Yahoo before writing this expectation.
      vi.mocked(fetchQuoteSummary).mockResolvedValue(
        quoteSummary({
          financialData: { revenueGrowth: 0.852, ebitdaMargins: 0.65294 },
        }),
      );
      vi.mocked(fetchAnnualRevenueSeries).mockResolvedValue([
        { date: '2024-01-31', operatingRevenue: 60_922_000_000 },
        { date: '2025-01-31', operatingRevenue: 130_497_000_000 },
        { date: '2026-01-31', operatingRevenue: 215_939_000_000 },
      ]);

      const result = await fetchAnalystConsensus(TICKER);

      expect(result.ok).toBe(true);
      if (!result.ok) return;
      // (215.939/130.497 - 1 + 0.65294) * 100 = 130.768
      expect(result.data.ruleOf40).toBeCloseTo(130.768, 2);
    });

    it('treats a genuine 0 annual revenue growth or 0 ebitdaMargins as a real value, not missing (falsy-zero regression guard)', async () => {
      // A flat-revenue, breakeven-EBITDA company: 0 + 0.4 = 40, not null.
      vi.mocked(fetchQuoteSummary).mockResolvedValue(
        quoteSummary({
          financialData: { revenueGrowth: 0, ebitdaMargins: 0.4 },
        }),
      );
      vi.mocked(fetchAnnualRevenueSeries).mockResolvedValue([
        { date: '2024-12-31', operatingRevenue: 1_000_000_000 },
        { date: '2025-12-31', operatingRevenue: 1_000_000_000 },
      ]);

      const result = await fetchAnalystConsensus(TICKER);

      expect(result.ok).toBe(true);
      if (!result.ok) return;
      expect(result.data.ruleOf40).toBeCloseTo(40, 10);
    });

    it('nulls ruleOf40 when ebitdaMargins is 0 but ebitda itself is absent (banks: Yahoo has no EBITDA concept for them, but reports a literal 0 margin instead of omitting the field -- live-confirmed against MS/JPM/BAC, all ebitda: undefined, ebitdaMargins: 0)', async () => {
      vi.mocked(fetchQuoteSummary).mockResolvedValue(
        quoteSummary({
          financialData: { revenueGrowth: 0.28, ebitdaMargins: 0, ebitda: undefined },
        }),
      );

      const result = await fetchAnalystConsensus(TICKER);

      expect(result.ok).toBe(true);
      if (!result.ok) return;
      // Previously this returned 28 (revenueGrowth alone, misread as a real Rule of 40 score) --
      // must be null instead, since there is no actual EBITDA data behind it.
      expect(result.data.ruleOf40).toBeNull();
    });

    it('nulls ruleOf40 when ebitdaMargins is 0 but ebitda is actually negative (live-confirmed against IONQ: ebitda: -793,051,008 on revenue of 246,474,000 -- a true margin of about -322%, not 0)', async () => {
      vi.mocked(fetchQuoteSummary).mockResolvedValue(
        quoteSummary({
          financialData: { revenueGrowth: 2.868, ebitdaMargins: 0, ebitda: -793_051_008 },
        }),
      );

      const result = await fetchAnalystConsensus(TICKER);

      expect(result.ok).toBe(true);
      if (!result.ok) return;
      // Previously this returned 286.80 with a "good" health badge for a company burning 3x its
      // revenue in EBITDA -- must be null, not a fabricated score in the opposite direction of
      // the truth.
      expect(result.data.ruleOf40).toBeNull();
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

    it('nulls ruleOf40 when fewer than 2 annual revenue points are available (period-mismatch fix: annual growth can no longer fall back to the quarterly financialData.revenueGrowth)', async () => {
      vi.mocked(fetchQuoteSummary).mockResolvedValue(
        quoteSummary({
          financialData: { revenueGrowth: 0.928, ebitdaMargins: 0.43253 },
        }),
      );
      vi.mocked(fetchAnnualRevenueSeries).mockResolvedValue([
        { date: '2025-12-31', operatingRevenue: 4_480_000_000 },
      ]);

      const result = await fetchAnalystConsensus(TICKER);

      expect(result.ok).toBe(true);
      if (!result.ok) return;
      expect(result.data.ruleOf40).toBeNull();
    });

    it('nulls ruleOf40 when fetchAnnualRevenueSeries returns no points at all', async () => {
      vi.mocked(fetchQuoteSummary).mockResolvedValue(
        quoteSummary({
          financialData: { revenueGrowth: 0.928, ebitdaMargins: 0.43253 },
        }),
      );
      vi.mocked(fetchAnnualRevenueSeries).mockResolvedValue([]);

      const result = await fetchAnalystConsensus(TICKER);

      expect(result.ok).toBe(true);
      if (!result.ok) return;
      expect(result.data.ruleOf40).toBeNull();
    });

    it('nulls ruleOf40 when fetchAnnualRevenueSeries rejects, without failing the overall request (auxiliary data source must degrade gracefully)', async () => {
      vi.mocked(fetchQuoteSummary).mockResolvedValue(
        quoteSummary({
          financialData: { revenueGrowth: 0.928, ebitdaMargins: 0.43253 },
        }),
      );
      vi.mocked(fetchAnnualRevenueSeries).mockRejectedValue(new Error('network down'));

      const result = await fetchAnalystConsensus(TICKER);

      expect(result.ok).toBe(true);
      if (!result.ok) return;
      expect(result.data.ruleOf40).toBeNull();
      // The rest of the consensus data must still come through unaffected -- trailingEps comes
      // from defaultKeyStatistics, untouched by this test's financialData override.
      expect(result.data.trailingEps).toBe(11.03);
    });

    it('period-mismatch regression guard: does not use the quarterly financialData.revenueGrowth for ruleOf40, even when it differs sharply from the true annual figure', async () => {
      // Real ANET-shaped figures: financialData.revenueGrowth (quarterly YoY) is 0.377, but
      // annual revenue 7.00B -> 9.01B is only 28.71 percent YoY -- live-confirmed mismatch.
      vi.mocked(fetchQuoteSummary).mockResolvedValue(
        quoteSummary({
          financialData: { revenueGrowth: 0.377, ebitdaMargins: 0.44016 },
        }),
      );
      vi.mocked(fetchAnnualRevenueSeries).mockResolvedValue([
        { date: '2024-12-31', operatingRevenue: 7_004_800_000 },
        { date: '2025-12-31', operatingRevenue: 9_012_100_000 },
      ]);

      const result = await fetchAnalystConsensus(TICKER);

      expect(result.ok).toBe(true);
      if (!result.ok) return;
      // (9012.1/7004.8 - 1 + 0.44016) * 100 is about 72.68, not (0.377 + 0.44016) * 100 = 81.72
      // (the quarterly-YoY-inflated figure this ticker actually showed before the fix).
      expect(result.data.ruleOf40).toBeCloseTo(72.68, 1);
      expect(result.data.ruleOf40).not.toBeCloseTo(81.72, 1);
    });
  });
});
