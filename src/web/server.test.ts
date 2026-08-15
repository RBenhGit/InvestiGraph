import { beforeEach, describe, expect, it, vi } from 'vitest';
import { buildServer } from './server';
import { fetchStockData } from '../data/twelvedata';
import { fetchAnalystConsensus } from '../data/yahoo';
import { calculateLynchValue } from '../valuation/lynch';
import { calculateRuleOneValue } from '../valuation/ruleOne';
import type { StockData } from '../data/twelvedata/types';
import type { AnalystConsensus } from '../data/yahoo/types';

vi.mock('../data/twelvedata', () => ({
  fetchStockData: vi.fn(),
}));

vi.mock('../data/yahoo', () => ({
  fetchAnalystConsensus: vi.fn(),
}));

const TICKER = 'AAPL';

function stockData(overrides: Partial<StockData> = {}): StockData {
  return {
    ticker: TICKER,
    epsTtm: 10,
    currentPrice: 200,
    currency: 'USD',
    growth: {
      historical1yPercent: 8,
      historical3yPercent: 9,
      historical5yPercent: 7,
      analystEstimate5yPercent: 10,
    },
    historicalPe: { avg1y: 20, avg3y: 22, avg5y: 25 },
    trailingPe: 20,
    providerReference: { trailingPe: 21, pegRatio: 1.5 },
    asOf: '2026-08-14T00:00:00.000Z',
    ...overrides,
  };
}

function analystConsensus(overrides: Partial<AnalystConsensus> = {}): AnalystConsensus {
  return {
    ticker: TICKER,
    nextYearEpsGrowthPercent: 12,
    priceTarget: { mean: 230, high: 280, low: 190, numberOfAnalysts: 40 },
    recommendationKey: 'buy',
    asOf: '2026-08-14T00:00:00.000Z',
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('POST /api/valuate', () => {
  it('returns 200 with fair values matching direct calls to the valuation functions', async () => {
    vi.mocked(fetchStockData).mockResolvedValue({ ok: true, data: stockData() });
    vi.mocked(fetchAnalystConsensus).mockResolvedValue({ ok: true, data: analystConsensus() });
    const fastify = buildServer();

    const growthRatePercent = 10;
    const exitPeMultiple = 15;
    const requiredReturnPercent = 15;
    const years = 10;

    const response = await fastify.inject({
      method: 'POST',
      url: '/api/valuate',
      payload: { ticker: TICKER, growthRatePercent, exitPeMultiple, requiredReturnPercent, years },
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.ok).toBe(true);

    const expectedLynch = calculateLynchValue(10, growthRatePercent);
    const expectedRuleOne = calculateRuleOneValue(
      10,
      growthRatePercent,
      exitPeMultiple,
      requiredReturnPercent,
      years,
    );
    expect(expectedLynch.ok).toBe(true);
    expect(expectedRuleOne.ok).toBe(true);
    if (!expectedLynch.ok || !expectedRuleOne.ok) return;

    expect(body.lynch.fairValue).toBe(expectedLynch.fairValue);
    expect(body.ruleOne.fairValue).toBe(expectedRuleOne.fairValue);
    expect(body.analystConsensus).toEqual(analystConsensus());
  });

  it('surfaces a non-2xx response with the error when fetchStockData fails', async () => {
    vi.mocked(fetchStockData).mockResolvedValue({
      ok: false,
      error: { type: 'NOT_FOUND', ticker: TICKER },
    });
    vi.mocked(fetchAnalystConsensus).mockResolvedValue({ ok: true, data: analystConsensus() });
    const fastify = buildServer();

    const response = await fastify.inject({
      method: 'POST',
      url: '/api/valuate',
      payload: {
        ticker: TICKER,
        growthRatePercent: 10,
        exitPeMultiple: 15,
        requiredReturnPercent: 15,
        years: 10,
      },
    });

    expect(response.statusCode).not.toBeLessThan(300);
    const body = response.json();
    expect(body.ok).toBe(false);
    expect(body.error).toEqual({ type: 'NOT_FOUND', ticker: TICKER });
  });

  it('still returns 200 with analystConsensus null when the Yahoo lookup fails', async () => {
    vi.mocked(fetchStockData).mockResolvedValue({ ok: true, data: stockData() });
    vi.mocked(fetchAnalystConsensus).mockResolvedValue({
      ok: false,
      error: { type: 'API_ERROR', ticker: TICKER, message: 'network timeout' },
    });
    const fastify = buildServer();

    const response = await fastify.inject({
      method: 'POST',
      url: '/api/valuate',
      payload: {
        ticker: TICKER,
        growthRatePercent: 10,
        exitPeMultiple: 15,
        requiredReturnPercent: 15,
        years: 10,
      },
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.ok).toBe(true);
    expect(body.analystConsensus).toBeNull();
  });

  it('still returns 200 with analystConsensus null when the Yahoo lookup throws', async () => {
    vi.mocked(fetchStockData).mockResolvedValue({ ok: true, data: stockData() });
    vi.mocked(fetchAnalystConsensus).mockRejectedValue(new Error('unexpected'));
    const fastify = buildServer();

    const response = await fastify.inject({
      method: 'POST',
      url: '/api/valuate',
      payload: {
        ticker: TICKER,
        growthRatePercent: 10,
        exitPeMultiple: 15,
        requiredReturnPercent: 15,
        years: 10,
      },
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.ok).toBe(true);
    expect(body.analystConsensus).toBeNull();
  });
});

describe('GET /', () => {
  it('serves the index HTML page', async () => {
    const fastify = buildServer();

    const response = await fastify.inject({ method: 'GET', url: '/' });

    expect(response.statusCode).toBe(200);
    expect(response.headers['content-type']).toContain('text/html');
  });
});
