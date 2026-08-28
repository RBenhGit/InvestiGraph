import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fetchStockData } from './index';
import {
  fetchAnnualIncomeStatement,
  fetchGrowthEstimates,
  fetchMonthlyTimeSeries,
  fetchQuarterlyIncomeStatement,
  fetchQuote,
  fetchStatistics,
} from './client';
import { TwelveDataResponseError } from './normalize';
import { getCachedStockData, saveCachedStockData } from '../cache';

vi.mock('./env', () => ({
  loadTwelveDataApiKey: () => 'test-key',
}));

vi.mock('../cache', () => ({
  saveCachedStockData: vi.fn(),
  getCachedStockData: vi.fn().mockResolvedValue(null),
}));

vi.mock('./client', () => ({
  fetchQuote: vi.fn(),
  fetchStatistics: vi.fn(),
  fetchGrowthEstimates: vi.fn(),
  fetchQuarterlyIncomeStatement: vi.fn(),
  fetchAnnualIncomeStatement: vi.fn(),
  fetchMonthlyTimeSeries: vi.fn(),
}));

const TICKER = 'AAPL';

/** Up to 8 quarters of round-number diluted EPS/shares: eps=2.5, shares=1,000,000,000 every
 * quarter => TTM net income 1e10, mean shares 1e9 => epsTtm = 10 for any 4-quarter window,
 * including the year-ago one calculateTtmEpsGrowthPercent needs. Paired with price=100 this
 * gives an easy-to-hand-verify trailingPe of 10. Callers wanting a non-zero epsTtmGrowthPercent
 * should build their own income_statement object directly rather than extend this shared fixture
 * (see 'computes epsTtmGrowthPercent...' below). */
function quarterlyIncome(count = 4) {
  const dates = [
    '2025-12-31',
    '2025-09-30',
    '2025-06-30',
    '2025-03-31',
    '2024-12-31',
    '2024-09-30',
    '2024-06-30',
    '2024-03-31',
  ].slice(0, count);
  return {
    income_statement: dates.map((fiscal_date) => ({
      fiscal_date,
      eps_diluted: 2.5,
      diluted_shares_outstanding: 1_000_000_000,
    })),
  };
}

/** 6 annual diluted-EPS entries (most-recent-first) chosen so the 1y and 3y CAGR windows land
 * on exactly 10% (1.21 * 1.1 = 1.331, and 1.0 * 1.1^3 = 1.331), plus 2 older years at a
 * constant 1.0 so a 5y CAGR and all three historicalPe windows have enough history to compute. */
function annualIncome() {
  return {
    income_statement: [
      { fiscal_date: '2025-12-31', eps_diluted: 1.331, diluted_shares_outstanding: 1_000_000_000 },
      { fiscal_date: '2024-12-31', eps_diluted: 1.21, diluted_shares_outstanding: 1_000_000_000 },
      { fiscal_date: '2023-12-31', eps_diluted: 1.1, diluted_shares_outstanding: 1_000_000_000 },
      { fiscal_date: '2022-12-31', eps_diluted: 1.0, diluted_shares_outstanding: 1_000_000_000 },
      { fiscal_date: '2021-12-31', eps_diluted: 1.0, diluted_shares_outstanding: 1_000_000_000 },
      { fiscal_date: '2020-12-31', eps_diluted: 1.0, diluted_shares_outstanding: 1_000_000_000 },
    ],
  };
}

/** Month-end closes covering every annualIncome() fiscal year-end, all at a constant 250 so
 * every historicalPe P/E point is 250/eps and easy to hand-verify. */
function monthlyTimeSeries(currency = 'USD') {
  return {
    meta: { currency },
    values: [
      { datetime: '2025-12-31', close: '250' },
      { datetime: '2024-12-31', close: '250' },
      { datetime: '2023-12-31', close: '250' },
      { datetime: '2022-12-31', close: '250' },
      { datetime: '2021-12-31', close: '250' },
      { datetime: '2020-12-31', close: '250' },
    ],
  };
}

function growthEstimates() {
  return { growth_estimates: { past_5_years_pa: 0.08, next_5_years_pa: 0.1 } };
}

function quote(currency = 'USD', close = '100') {
  return { symbol: TICKER, currency, close };
}

function statistics() {
  return { statistics: { valuations_metrics: {} } };
}

function mockAllSuccess(
  overrides: {
    quote?: ReturnType<typeof quote>;
    quarterlyIncome?: ReturnType<typeof quarterlyIncome>;
    monthlyTimeSeries?: ReturnType<typeof monthlyTimeSeries>;
  } = {},
) {
  vi.mocked(fetchQuote).mockResolvedValue(overrides.quote ?? quote());
  vi.mocked(fetchStatistics).mockResolvedValue(statistics());
  vi.mocked(fetchGrowthEstimates).mockResolvedValue(growthEstimates());
  vi.mocked(fetchQuarterlyIncomeStatement).mockResolvedValue(
    overrides.quarterlyIncome ?? quarterlyIncome(),
  );
  vi.mocked(fetchAnnualIncomeStatement).mockResolvedValue(annualIncome());
  vi.mocked(fetchMonthlyTimeSeries).mockResolvedValue(
    overrides.monthlyTimeSeries ?? monthlyTimeSeries(),
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('fetchStockData', () => {
  it('assembles a full StockData from a successful mocked response set', async () => {
    mockAllSuccess();

    const result = await fetchStockData(TICKER);

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.data.ticker).toBe(TICKER);
    expect(result.data.currentPrice).toBe(100);
    expect(result.data.currency).toBe('USD');
    expect(result.data.epsTtm).toBe(10);
    expect(result.data.trailingPe).toBe(10);
    expect(result.data.growth.historical1yPercent).toBeCloseTo(10, 10);
    expect(result.data.growth.historical3yPercent).toBeCloseTo(10, 10);
    // growth_estimates is present in this fixture, so historical5yPercent prefers its
    // past_5_years_pa (8%) over the locally-computed fallback CAGR.
    expect(result.data.growth.historical5yPercent).toBeCloseTo(8, 10);
    expect(result.data.growth.analystEstimate5yPercent).toBeCloseTo(10, 10);
    // 6 years of annual EPS/price, all P/E points = 250/eps. avg1y = 250/1.331 ≈ 187.83;
    // avg3y/avg5y are medians over the 3/5 most recent annual P/E points.
    expect(result.data.historicalPe.avg1y).toBeCloseTo(250 / 1.331, 10);
    expect(result.data.historicalPe.avg3y).not.toBeNull();
    expect(result.data.historicalPe.avg5y).not.toBeNull();
    // statistics() fixture has no trailing_pe, so there's nothing to compare epsTtm's
    // implied P/E against — detectStaleTtmEps must not fire on a missing provider figure.
    expect(result.data.staleTtmWarning).toBe(false);
    // mockAllSuccess()'s default quarterlyIncome() count (4) is one full TTM window, not the 8
    // quarters calculateTtmEpsGrowthPercent needs for a true year-over-year comparison — null is
    // the correct, honest result here (matches this plan tier's real-world behavior today).
    expect(result.data.growth.epsTtmGrowthPercent).toBeNull();
  });

  it('leaves epsTtmGrowthPercent null with fewer than 8 quarters (this plan tier caps at 6)', async () => {
    mockAllSuccess({ quarterlyIncome: quarterlyIncome(6) });

    const result = await fetchStockData(TICKER);

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    // epsTtm/trailingPe are unaffected -- resolveTtmEps only ever needs the first 4 quarters.
    expect(result.data.epsTtm).toBe(10);
    expect(result.data.growth.epsTtmGrowthPercent).toBeNull();
  });

  it('computes epsTtmGrowthPercent when a full 8 quarters are available', async () => {
    // Hand-built rather than quarterlyIncome() (which returns a flat epsTtm=10 in every window,
    // making a growth-rate assertion trivially 0% and not a real regression check): current TTM
    // (Q1-Q4 at 3.0 each = 12.0) vs. year-ago TTM (Q5-Q8 at 2.0 each = 8.0) => growth = 50%.
    const eightQuarters = {
      income_statement: [
        { fiscal_date: '2025-12-31', eps_diluted: 3.0, diluted_shares_outstanding: 1_000_000_000 },
        { fiscal_date: '2025-09-30', eps_diluted: 3.0, diluted_shares_outstanding: 1_000_000_000 },
        { fiscal_date: '2025-06-30', eps_diluted: 3.0, diluted_shares_outstanding: 1_000_000_000 },
        { fiscal_date: '2025-03-31', eps_diluted: 3.0, diluted_shares_outstanding: 1_000_000_000 },
        { fiscal_date: '2024-12-31', eps_diluted: 2.0, diluted_shares_outstanding: 1_000_000_000 },
        { fiscal_date: '2024-09-30', eps_diluted: 2.0, diluted_shares_outstanding: 1_000_000_000 },
        { fiscal_date: '2024-06-30', eps_diluted: 2.0, diluted_shares_outstanding: 1_000_000_000 },
        { fiscal_date: '2024-03-31', eps_diluted: 2.0, diluted_shares_outstanding: 1_000_000_000 },
      ],
    };
    mockAllSuccess({ quarterlyIncome: eightQuarters });

    const result = await fetchStockData(TICKER);

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.data.epsTtm).toBe(12);
    expect(result.data.growth.epsTtmGrowthPercent).toBeCloseTo(50, 10);
  });

  it('flags staleTtmWarning when computed trailingPe diverges >5% from the provider trailing P/E', async () => {
    // epsTtm=10, price=100 => trailingPe=10 (from mockAllSuccess's quarterlyIncome()/quote()
    // fixtures). A provider trailing_pe of 20 implies epsTtm should be ~5 — a >5% divergence
    // from the app's computed epsTtm=10, mirroring the real CSCO case this guard was built for
    // (Twelve Data's income_statement lagging behind its own statistics endpoint).
    vi.mocked(fetchQuote).mockResolvedValue(quote());
    vi.mocked(fetchStatistics).mockResolvedValue({
      statistics: { valuations_metrics: { trailing_pe: 20 } },
    });
    vi.mocked(fetchGrowthEstimates).mockResolvedValue(growthEstimates());
    vi.mocked(fetchQuarterlyIncomeStatement).mockResolvedValue(quarterlyIncome());
    vi.mocked(fetchAnnualIncomeStatement).mockResolvedValue(annualIncome());
    vi.mocked(fetchMonthlyTimeSeries).mockResolvedValue(monthlyTimeSeries());

    const result = await fetchStockData(TICKER);

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.data.trailingPe).toBe(10);
    expect(result.data.providerReference.trailingPe).toBe(20);
    expect(result.data.staleTtmWarning).toBe(true);
  });

  it('does not flag staleTtmWarning when computed and provider trailing P/E roughly agree', async () => {
    mockAllSuccess();
    vi.mocked(fetchStatistics).mockResolvedValue({
      statistics: { valuations_metrics: { trailing_pe: 10.4 } }, // within 5% of computed 10
    });

    const result = await fetchStockData(TICKER);

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.data.staleTtmWarning).toBe(false);
  });

  it('maps a thrown client error to API_ERROR by default', async () => {
    mockAllSuccess();
    vi.mocked(fetchQuote).mockRejectedValue(
      new TwelveDataResponseError('API_ERROR', 'quote', 'rate limit exceeded'),
    );

    const result = await fetchStockData(TICKER);

    expect(result).toEqual({
      ok: false,
      error: {
        type: 'API_ERROR',
        ticker: TICKER,
        endpoint: 'quote',
        message: 'rate limit exceeded',
      },
    });
  });

  it('infers NOT_FOUND when the API error message signals an unknown symbol', async () => {
    mockAllSuccess();
    vi.mocked(fetchQuote).mockRejectedValue(
      new TwelveDataResponseError('API_ERROR', 'quote', 'symbol not found: NOTATICKER'),
    );

    const result = await fetchStockData(TICKER);

    expect(result).toEqual({ ok: false, error: { type: 'NOT_FOUND', ticker: TICKER } });
  });

  it('reports INVALID_CURRENCY_UNIT when quote and fundamentals currencies disagree', async () => {
    mockAllSuccess({ monthlyTimeSeries: monthlyTimeSeries('EUR') });

    const result = await fetchStockData(TICKER);

    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.error.type).toBe('INVALID_CURRENCY_UNIT');
  });

  it('falls back to a locally-computed 5y CAGR when growth_estimates is unavailable (e.g. plan-gated 403)', async () => {
    mockAllSuccess();
    vi.mocked(fetchGrowthEstimates).mockRejectedValue(
      new TwelveDataResponseError(
        'API_ERROR',
        'growth_estimates',
        '/growth_estimates is available exclusively with ultra or enterprise plans',
      ),
    );

    const result = await fetchStockData(TICKER);

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.data.epsTtm).toBe(10);
    expect(result.data.growth.historical1yPercent).toBeCloseTo(10, 10);
    expect(result.data.growth.historical3yPercent).toBeCloseTo(10, 10);
    // No growth_estimates: historical5yPercent falls back to the local CAGR from
    // annualIncome()'s EPS series — 1.331 vs. 1.0 five years earlier.
    const expectedLocal5y = (Math.pow(1.331 / 1.0, 1 / 5) - 1) * 100;
    expect(result.data.growth.historical5yPercent).toBeCloseTo(expectedLocal5y, 10);
    expect(result.data.growth.analystEstimate5yPercent).toBeNull();
  });

  it('reports INSUFFICIENT_DATA when there is not enough quarterly data to resolve TTM EPS', async () => {
    mockAllSuccess({ quarterlyIncome: quarterlyIncome(2) });

    const result = await fetchStockData(TICKER);

    expect(result).toEqual({
      ok: false,
      error: { type: 'INSUFFICIENT_DATA', ticker: TICKER, reason: 'unable to resolve TTM EPS' },
    });
  });

  it('falls back to cached stock data when API call fails', async () => {
    mockAllSuccess();
    vi.mocked(fetchQuote).mockRejectedValue(
      new TwelveDataResponseError('RATE_LIMIT', 'quote'),
    );
    const mockCached = {
      ticker: TICKER,
      epsTtm: 5,
      currentPrice: 150,
      currency: 'USD',
      growth: {
        historical1yPercent: 8,
        historical3yPercent: 9,
        historical5yPercent: 10,
        analystEstimate5yPercent: 12,
        epsTtmGrowthPercent: null,
      },
      historicalPe: { avg1y: 20, avg3y: 22, avg5y: 24 },
      trailingPe: 30,
      providerReference: { trailingPe: 30, pegRatio: 2.5 },
      staleTtmWarning: false,
      asOf: '2026-08-19T12:00:00.000Z',
    };
    vi.mocked(getCachedStockData).mockResolvedValue(mockCached);

    const result = await fetchStockData(TICKER);

    expect(result).toEqual({ ok: true, data: mockCached });
  });

  it('returns cached stock data directly without calling API when cache is fresh', async () => {
    const mockCached = {
      ticker: TICKER,
      epsTtm: 5,
      currentPrice: 150,
      currency: 'USD',
      growth: {
        historical1yPercent: 8,
        historical3yPercent: 9,
        historical5yPercent: 10,
        analystEstimate5yPercent: 12,
        epsTtmGrowthPercent: null,
      },
      historicalPe: { avg1y: 20, avg3y: 22, avg5y: 24 },
      trailingPe: 30,
      providerReference: { trailingPe: 30, pegRatio: 2.5 },
      staleTtmWarning: false,
      asOf: new Date().toISOString(),
    };
    vi.mocked(getCachedStockData).mockResolvedValue(mockCached);

    const result = await fetchStockData(TICKER);

    expect(result).toEqual({ ok: true, data: mockCached });
    expect(fetchQuote).not.toHaveBeenCalled();
    expect(fetchStatistics).not.toHaveBeenCalled();
  });

  it('bypasses cache when forceRefresh is true', async () => {
    mockAllSuccess();
    const mockCached = {
      ticker: TICKER,
      epsTtm: 5,
      currentPrice: 150,
      currency: 'USD',
      growth: {
        historical1yPercent: 8,
        historical3yPercent: 9,
        historical5yPercent: 10,
        analystEstimate5yPercent: 12,
        epsTtmGrowthPercent: null,
      },
      historicalPe: { avg1y: 20, avg3y: 22, avg5y: 24 },
      trailingPe: 30,
      providerReference: { trailingPe: 30, pegRatio: 2.5 },
      staleTtmWarning: false,
      asOf: new Date().toISOString(),
    };
    vi.mocked(getCachedStockData).mockResolvedValue(mockCached);

    const result = await fetchStockData(TICKER, { forceRefresh: true });

    expect(result.ok).toBe(true);
    expect(fetchQuote).toHaveBeenCalled();
    expect(saveCachedStockData).toHaveBeenCalled();
  });

  it('saves to cache on successful fetch', async () => {
    mockAllSuccess();
    vi.mocked(getCachedStockData).mockResolvedValue(null);

    const result = await fetchStockData(TICKER);

    expect(result.ok).toBe(true);
    expect(saveCachedStockData).toHaveBeenCalledWith(TICKER, expect.objectContaining({ ticker: TICKER }));
  });
});
