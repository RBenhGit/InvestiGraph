import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  fetchAnnualIncomeStatement,
  fetchGrowthEstimates,
  fetchMonthlyTimeSeries,
  fetchQuarterlyIncomeStatement,
  fetchQuote,
  fetchStatistics,
} from './client';
import { TwelveDataResponseError } from './normalize';

const API_KEY = 'test-key';
const TICKER = 'AAPL';

/** A minimal `fetch` Response stand-in — only the members `client.ts` actually reads. */
function mockResponse(
  body: unknown,
  init: { ok?: boolean; status?: number; statusText?: string } = {},
) {
  return {
    ok: init.ok ?? true,
    status: init.status ?? 200,
    statusText: init.statusText ?? 'OK',
    json: async () => body,
  };
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('fetchQuote', () => {
  it('parses a successful response into the expected shape', async () => {
    const body = { symbol: 'AAPL', currency: 'USD', close: '305.955' };
    fetchMock.mockResolvedValue(mockResponse(body));

    const result = await fetchQuote(TICKER, API_KEY);

    expect(result).toEqual(body);
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toBe('https://api.twelvedata.com/quote?symbol=AAPL&apikey=test-key');
  });

  it('throws on a status:"error" body', async () => {
    fetchMock.mockResolvedValue(mockResponse({ status: 'error', message: 'symbol not found' }));

    await expect(fetchQuote(TICKER, API_KEY)).rejects.toThrow(TwelveDataResponseError);
  });

  it('throws on a non-2xx HTTP status', async () => {
    fetchMock.mockResolvedValue(
      mockResponse(
        { status: 'error', message: 'unauthorized' },
        { ok: false, status: 401, statusText: 'Unauthorized' },
      ),
    );

    await expect(fetchQuote(TICKER, API_KEY)).rejects.toThrow(TwelveDataResponseError);
  });
});

describe('fetchStatistics', () => {
  it('parses a successful response into the expected shape', async () => {
    const body = { statistics: { valuations_metrics: { trailing_pe: 34.61, peg_ratio: 1.18 } } };
    fetchMock.mockResolvedValue(mockResponse(body));

    const result = await fetchStatistics(TICKER, API_KEY);

    expect(result).toEqual(body);
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toBe('https://api.twelvedata.com/statistics?symbol=AAPL&apikey=test-key');
  });

  it('throws on an empty object body', async () => {
    fetchMock.mockResolvedValue(mockResponse({}));

    await expect(fetchStatistics(TICKER, API_KEY)).rejects.toThrow(TwelveDataResponseError);
  });
});

describe('fetchGrowthEstimates', () => {
  it('parses a successful response into the expected shape', async () => {
    const body = {
      growth_estimates: { past_5_years_pa: 0.092148273162, next_5_years_pa: 0.086637550391 },
    };
    fetchMock.mockResolvedValue(mockResponse(body));

    const result = await fetchGrowthEstimates(TICKER, API_KEY);

    expect(result).toEqual(body);
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toBe('https://api.twelvedata.com/growth_estimates?symbol=AAPL&apikey=test-key');
  });

  it('throws on a non-2xx HTTP status', async () => {
    fetchMock.mockResolvedValue(
      mockResponse(null, { ok: false, status: 500, statusText: 'Internal Server Error' }),
    );

    await expect(fetchGrowthEstimates(TICKER, API_KEY)).rejects.toThrow(TwelveDataResponseError);
  });
});

describe('fetchQuarterlyIncomeStatement', () => {
  it('parses a successful response and requests outputsize=6, period=quarterly', async () => {
    const body = {
      meta: {},
      income_statement: [
        { fiscal_date: '2026-06-30', eps_diluted: 2.02, diluted_shares_outstanding: 14714676000 },
        { fiscal_date: '2026-03-31', eps_diluted: 1.95, diluted_shares_outstanding: 14700000000 },
      ],
    };
    fetchMock.mockResolvedValue(mockResponse(body));

    const result = await fetchQuarterlyIncomeStatement(TICKER, API_KEY);

    expect(result).toEqual(body);
    const url = fetchMock.mock.calls[0][0] as string;
    // 6 (not 4) is this plan tier's real ceiling -- requested in full so
    // calculateTtmEpsGrowthPercent gets as many quarters as this plan allows, even though it
    // still needs 8 for a true YoY TTM figure and returns null until the plan is upgraded.
    expect(url).toBe(
      'https://api.twelvedata.com/income_statement?symbol=AAPL&period=quarterly&outputsize=6&apikey=test-key',
    );
  });

  it('throws on a status:"error" body', async () => {
    fetchMock.mockResolvedValue(mockResponse({ status: 'error', message: 'symbol not found' }));

    await expect(fetchQuarterlyIncomeStatement(TICKER, API_KEY)).rejects.toThrow(
      TwelveDataResponseError,
    );
  });
});

describe('fetchAnnualIncomeStatement', () => {
  it('parses a successful response and requests outputsize=6, period=annual', async () => {
    const body = {
      meta: {},
      income_statement: [
        { fiscal_date: '2025-12-31', eps_diluted: 7.5, diluted_shares_outstanding: 14700000000 },
      ],
    };
    fetchMock.mockResolvedValue(mockResponse(body));

    const result = await fetchAnnualIncomeStatement(TICKER, API_KEY);

    expect(result).toEqual(body);
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toBe(
      'https://api.twelvedata.com/income_statement?symbol=AAPL&period=annual&outputsize=6&apikey=test-key',
    );
  });

  it('throws on an empty array body', async () => {
    fetchMock.mockResolvedValue(mockResponse({ income_statement: [] }));
    // Note: assertNonEmpty only special-cases a bare [] or {} as empty; a populated envelope
    // object with an empty array field inside it is not itself considered empty. This test
    // documents that the top-level object still passes through — array-emptiness of a nested
    // field is the caller's (index.ts's) concern, not client.ts's.
    await expect(fetchAnnualIncomeStatement(TICKER, API_KEY)).resolves.toEqual({
      income_statement: [],
    });
  });
});

describe('fetchMonthlyTimeSeries', () => {
  it('parses a successful response and requests interval=1month, outputsize=61', async () => {
    const body = {
      meta: {},
      values: [
        {
          datetime: '2026-08-01',
          open: '309.57999',
          high: '316.29001',
          low: '300.57001',
          close: '305.955',
          volume: '436279222',
        },
      ],
      status: 'ok',
    };
    fetchMock.mockResolvedValue(mockResponse(body));

    const result = await fetchMonthlyTimeSeries(TICKER, API_KEY);

    expect(result).toEqual(body);
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toBe(
      'https://api.twelvedata.com/time_series?symbol=AAPL&interval=1month&outputsize=61&apikey=test-key',
    );
  });

  it('throws on a status:"error" body', async () => {
    fetchMock.mockResolvedValue(mockResponse({ status: 'error', message: 'symbol not found' }));

    await expect(fetchMonthlyTimeSeries(TICKER, API_KEY)).rejects.toThrow(TwelveDataResponseError);
  });
});
