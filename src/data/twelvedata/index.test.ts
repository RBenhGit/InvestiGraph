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

vi.mock('./env', () => ({
  loadTwelveDataApiKey: () => 'test-key',
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

/** 4 quarters of round-number diluted EPS/shares: eps=2.5, shares=1,000,000,000 each quarter
 * => TTM net income 1e10, mean shares 1e9 => epsTtm = 10. Paired with price=100 this gives an
 * easy-to-hand-verify trailingPe of 10. */
function quarterlyIncome(count = 4) {
  const dates = ['2025-12-31', '2025-09-30', '2025-06-30', '2025-03-31'].slice(0, count);
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
});
