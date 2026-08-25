import { beforeEach, describe, expect, it, vi } from 'vitest';
import { buildServer } from './server';
import { fetchStockData } from '../data/twelvedata';
import { fetchAnalystConsensus } from '../data/yahoo';
import { calculateLynchValue } from '../valuation/lynch';
import { calculateRuleOneValue } from '../valuation/ruleOne';
import { saveValuation, getHistory, deleteValuation } from '../history';
import type { StockData } from '../data/twelvedata/types';
import type { AnalystConsensus } from '../data/yahoo/types';

vi.mock('../data/twelvedata', () => ({
  fetchStockData: vi.fn(),
}));

vi.mock('../data/yahoo', () => ({
  fetchAnalystConsensus: vi.fn(),
}));

vi.mock('../history', () => ({
  saveValuation: vi.fn(),
  getHistory: vi.fn(),
  deleteValuation: vi.fn(),
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
    staleTtmWarning: false,
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
    beta: null,
    priceToSales: null,
    ruleOf40: null,
    trailingEps: null,
    mostRecentQuarterEndDate: null,
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

    expect(body.lynch.base.fairValue).toBe(expectedLynch.fairValue);
    expect(body.ruleOne.base.fairValue).toBe(expectedRuleOne.fairValue);
    expect(body.analystConsensus).toEqual(analystConsensus());
  });

  it('passes mosPercent to calculateRuleOneValue when provided', async () => {
    vi.mocked(fetchStockData).mockResolvedValue({ ok: true, data: stockData() });
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
        mosPercent: 25,
      },
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.ok).toBe(true);
    const expectedRuleOne = calculateRuleOneValue(10, 10, 15, 15, 10, 25);
    if (expectedRuleOne.ok) {
      expect(body.ruleOne.base.fairValue).toBe(expectedRuleOne.fairValue);
    }
  });

  it('uses the bear/bull growth, exit-P/E, and required-return the user actually provided, not hardcoded defaults', async () => {
    // Regression test: bear/bull scenarios previously ignored bearExitPeMultiple/bullExitPeMultiple
    // etc. entirely and used fixed constants no matter what the request sent. Growth is now also
    // independently editable per scenario (bearGrowthRatePercent/bullGrowthRatePercent) rather
    // than always auto-derived from base. MoS is shared -- one value for all three scenarios.
    vi.mocked(fetchStockData).mockResolvedValue({ ok: true, data: stockData() });
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
        mosPercent: 25,
        // Deliberately not the old hardcoded/derived defaults, so this fails loudly if they leak back in.
        bearGrowthRatePercent: 3,
        bearExitPeMultiple: 8,
        bearRequiredReturnPercent: 18,
        bullGrowthRatePercent: 19,
        bullExitPeMultiple: 22,
        bullRequiredReturnPercent: 11,
      },
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.ok).toBe(true);

    expect(body.ruleOne.bear.ok).toBe(true);
    expect(body.ruleOne.bear.inputs.growthRatePercentClamped).toBe(3);
    expect(body.ruleOne.bear.inputs.exitPeMultiple).toBe(8);
    expect(body.ruleOne.bear.inputs.requiredReturnPercent).toBe(18);
    expect(body.ruleOne.bear.inputs.mosPercent).toBe(25);

    expect(body.ruleOne.bull.ok).toBe(true);
    expect(body.ruleOne.bull.inputs.growthRatePercentClamped).toBe(19);
    expect(body.ruleOne.bull.inputs.exitPeMultiple).toBe(22);
    expect(body.ruleOne.bull.inputs.requiredReturnPercent).toBe(11);
    expect(body.ruleOne.bull.inputs.mosPercent).toBe(25);

    const expectedBear = calculateRuleOneValue(10, 3, 8, 18, 10, 25);
    const expectedBull = calculateRuleOneValue(10, 19, 22, 11, 10, 25);
    expect(expectedBear.ok).toBe(true);
    expect(expectedBull.ok).toBe(true);
    if (expectedBear.ok) expect(body.ruleOne.bear.fairValue).toBe(expectedBear.fairValue);
    if (expectedBull.ok) expect(body.ruleOne.bull.fairValue).toBe(expectedBull.fairValue);
  });

  it('derives bear/bull growth from the base scenario and falls back to sane defaults when the request omits the bear/bull fields', async () => {
    vi.mocked(fetchStockData).mockResolvedValue({ ok: true, data: stockData() });
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
        // bear*/bull* fields omitted entirely, as an older client would send
      },
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.ruleOne.bear.inputs.growthRatePercentClamped).toBe(7.5); // 10 * 0.75, derived
    expect(body.ruleOne.bear.inputs.exitPeMultiple).toBe(10);
    expect(body.ruleOne.bear.inputs.requiredReturnPercent).toBe(15);
    expect(body.ruleOne.bear.inputs.mosPercent).toBe(0); // mosPercent omitted -> shared default 0
    expect(body.ruleOne.bull.inputs.growthRatePercentClamped).toBe(12.5); // 10 * 1.25, derived
    expect(body.ruleOne.bull.inputs.exitPeMultiple).toBe(20);
    expect(body.ruleOne.bull.inputs.requiredReturnPercent).toBe(12);
    expect(body.ruleOne.bull.inputs.mosPercent).toBe(0);
  });

  it('forwards forceRefresh to data fetchers when requested', async () => {
    vi.mocked(fetchStockData).mockResolvedValue({ ok: true, data: stockData() });
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
        forceRefresh: true,
      },
    });

    expect(response.statusCode).toBe(200);
    expect(fetchStockData).toHaveBeenCalledWith(TICKER, { forceRefresh: true });
    expect(fetchAnalystConsensus).toHaveBeenCalledWith(TICKER, { forceRefresh: true });
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

  it('uses epsTtm as-is (source twelvedata) when staleTtmWarning is false, even if Yahoo has a different trailingEps', async () => {
    vi.mocked(fetchStockData).mockResolvedValue({
      ok: true,
      data: stockData({ epsTtm: 10, staleTtmWarning: false }),
    });
    vi.mocked(fetchAnalystConsensus).mockResolvedValue({
      ok: true,
      data: analystConsensus({ trailingEps: 12 }),
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

    const body = response.json();
    expect(body.effectiveEps).toBe(10);
    expect(body.epsSource).toBe('twelvedata');
  });

  it('falls back to Yahoo trailingEps (source yahoo-fallback) when staleTtmWarning is true and Yahoo succeeds', async () => {
    vi.mocked(fetchStockData).mockResolvedValue({
      ok: true,
      data: stockData({ epsTtm: 3.08, staleTtmWarning: true }),
    });
    vi.mocked(fetchAnalystConsensus).mockResolvedValue({
      ok: true,
      data: analystConsensus({ trailingEps: 3.31, mostRecentQuarterEndDate: '2026-07-25T00:00:00.000Z' }),
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

    const body = response.json();
    expect(body.effectiveEps).toBe(3.31);
    expect(body.epsSource).toBe('yahoo-fallback');
    expect(body.epsSourceDetail).toContain('Yahoo Finance');
  });

  it('keeps the stale Twelve Data epsTtm (source twelvedata-stale-no-fallback) when staleTtmWarning is true and Yahoo fails', async () => {
    vi.mocked(fetchStockData).mockResolvedValue({
      ok: true,
      data: stockData({ epsTtm: 3.08, staleTtmWarning: true }),
    });
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

    const body = response.json();
    expect(body.effectiveEps).toBe(3.08);
    expect(body.epsSource).toBe('twelvedata-stale-no-fallback');
  });

  it('an explicit epsOverride still wins over the resolved (possibly Yahoo-fallback) eps, with epsSource null', async () => {
    vi.mocked(fetchStockData).mockResolvedValue({
      ok: true,
      data: stockData({ epsTtm: 3.08, staleTtmWarning: true }),
    });
    vi.mocked(fetchAnalystConsensus).mockResolvedValue({
      ok: true,
      data: analystConsensus({ trailingEps: 3.31 }),
    });
    const fastify = buildServer();

    const response = await fastify.inject({
      method: 'POST',
      url: '/api/valuate',
      payload: {
        ticker: TICKER,
        epsOverride: 5,
        growthRatePercent: 10,
        exitPeMultiple: 15,
        requiredReturnPercent: 15,
        years: 10,
      },
    });

    const body = response.json();
    expect(body.effectiveEps).toBe(5);
    expect(body.epsSource).toBeNull();
  });

  it('seeds growth from historical3yPercent uncapped when analyst estimate is missing, matching the CLI fallback chain exactly', async () => {
    // historical3yPercent (22) exceeds the old undocumented 15% web-only cap — this proves
    // the cap is gone and the web adapter now uses the exact same fallback chain as the CLI
    // (analystEstimate5y ?? historical3y ?? historical1y), with no extra transformation.
    vi.mocked(fetchStockData).mockResolvedValue({
      ok: true,
      data: stockData({
        growth: {
          historical1yPercent: 8,
          historical3yPercent: 22,
          historical5yPercent: 7,
          analystEstimate5yPercent: null,
        },
      }),
    });
    vi.mocked(fetchAnalystConsensus).mockResolvedValue({ ok: true, data: analystConsensus() });
    const fastify = buildServer();

    const response = await fastify.inject({
      method: 'POST',
      url: '/api/valuate',
      payload: {
        ticker: TICKER,
        exitPeMultiple: 15,
        requiredReturnPercent: 15,
        years: 10,
        // growthRatePercent omitted: server must seed it itself, same as leaving the web form blank
      },
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.ok).toBe(true);
    expect(body.effectiveGrowth).toBe(22);

    const expectedLynch = calculateLynchValue(10, 22);
    expect(expectedLynch.ok).toBe(true);
    if (expectedLynch.ok) {
      expect(body.lynch.base.fairValue).toBe(expectedLynch.fairValue);
    }
  });

  it('returns MISSING_GROWTH_RATE (not a fabricated 0%) when no growth data is available at all', async () => {
    // All three growth fields null and no manual growthRatePercent provided: this must behave
    // like the CLI does in the same situation (surface an error), not silently default to 0
    // and return an ok:true response with a fake $0 fair value.
    vi.mocked(fetchStockData).mockResolvedValue({
      ok: true,
      data: stockData({
        growth: {
          historical1yPercent: null,
          historical3yPercent: null,
          historical5yPercent: null,
          analystEstimate5yPercent: null,
        },
      }),
    });
    vi.mocked(fetchAnalystConsensus).mockResolvedValue({ ok: true, data: analystConsensus() });
    const fastify = buildServer();

    const response = await fastify.inject({
      method: 'POST',
      url: '/api/valuate',
      payload: {
        ticker: TICKER,
        exitPeMultiple: 15,
        requiredReturnPercent: 15,
        years: 10,
      },
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.ok).toBe(true);
    expect(body.effectiveGrowth).toBeNull();
    const missingGrowth = { ok: false, error: 'MISSING_GROWTH_RATE' };
    expect(body.lynch).toEqual({ base: missingGrowth, bear: missingGrowth, bull: missingGrowth });
    expect(body.ruleOne).toEqual({ base: missingGrowth, bear: missingGrowth, bull: missingGrowth });
  });

  // Regression: ValuateRequestBody is a TypeScript interface, i.e. compile-time only. Nothing
  // validated request.body at runtime, so a malformed ticker reached fetchStockData and blew up
  // inside it -- returning a raw 500 ("Cannot read properties of...", "ticker.toUpperCase is
  // not a function") that leaked internal error text instead of this codebase's typed
  // { ok: false, error } shape. An API caller (or an older/buggy client) can send any of these.
  it.each([
    ['a missing ticker', {}],
    ['a null ticker', { ticker: null }],
    ['a numeric ticker', { ticker: 12345 }],
    ['an object ticker', { ticker: { evil: true } }],
    ['a whitespace-only ticker', { ticker: '   ' }],
  ])('returns a typed 400 (not an unhandled 500) for %s', async (_label, payload) => {
    vi.mocked(fetchStockData).mockResolvedValue({ ok: true, data: stockData() });
    vi.mocked(fetchAnalystConsensus).mockResolvedValue({ ok: true, data: analystConsensus() });
    const fastify = buildServer();

    const response = await fastify.inject({
      method: 'POST',
      url: '/api/valuate',
      payload: { exitPeMultiple: 15, requiredReturnPercent: 15, years: 10, ...(payload as object) },
    });

    expect(response.statusCode).toBe(400);
    const body = response.json();
    expect(body.ok).toBe(false);
    expect(body.error.type).toBe('INSUFFICIENT_DATA');
    // The whole point: a typed error, not a leaked stack/TypeError message.
    expect(body.error.reason).toMatch(/ticker/i);
    expect(JSON.stringify(body)).not.toMatch(/Cannot read propert|is not a function/);
    // A request rejected at the door must never have reached the data layer.
    expect(fetchStockData).not.toHaveBeenCalled();
  });

  it('still accepts a valid ticker that needs trimming/upper-casing', async () => {
    vi.mocked(fetchStockData).mockResolvedValue({ ok: true, data: stockData() });
    vi.mocked(fetchAnalystConsensus).mockResolvedValue({ ok: true, data: analystConsensus() });
    const fastify = buildServer();

    const response = await fastify.inject({
      method: 'POST',
      url: '/api/valuate',
      payload: { ticker: '  aapl  ', exitPeMultiple: 15, requiredReturnPercent: 15, years: 10 },
    });

    expect(response.statusCode).toBe(200);
    expect(response.json().ok).toBe(true);
    // Regression: the ticker used to be forwarded to the data layer/cache verbatim (padding and
    // all). Both calls must receive the normalized ("AAPL") form, not "  aapl  ".
    expect(fetchStockData).toHaveBeenCalledWith('AAPL', { forceRefresh: undefined });
    expect(fetchAnalystConsensus).toHaveBeenCalledWith('AAPL', { forceRefresh: undefined });
  });

  // Regression: request.body is typed ValuateRequestBody at compile time only. A bodyless POST
  // or a literal JSON `null` body reached the destructuring assignment before any guard ran and
  // threw ("Cannot destructure property 'ticker' of ... as it is undefined/null"), surfacing as
  // an unhandled 500 -- the exact failure class this file's other malformed-ticker tests above
  // were written to close, just one step earlier in the request.
  it('returns a typed 400 (not an unhandled 500) for a missing request body', async () => {
    const fastify = buildServer();

    const response = await fastify.inject({ method: 'POST', url: '/api/valuate' });

    expect(response.statusCode).toBe(400);
    const body = response.json();
    expect(body.ok).toBe(false);
    expect(body.error.type).toBe('INSUFFICIENT_DATA');
    expect(JSON.stringify(body)).not.toMatch(/Cannot destructure|is not a function/);
    expect(fetchStockData).not.toHaveBeenCalled();
  });

  it('returns a typed 400 (not an unhandled 500) for a literal null request body', async () => {
    const fastify = buildServer();

    const response = await fastify.inject({
      method: 'POST',
      url: '/api/valuate',
      payload: 'null',
      headers: { 'content-type': 'application/json' },
    });

    expect(response.statusCode).toBe(400);
    const body = response.json();
    expect(body.ok).toBe(false);
    expect(body.error.type).toBe('INSUFFICIENT_DATA');
    expect(JSON.stringify(body)).not.toMatch(/Cannot destructure|is not a function/);
    expect(fetchStockData).not.toHaveBeenCalled();
  });

  // Regression: server.ts's ticker guard used to accept any non-blank string, but
  // src/data/cache.ts's safeTickerSegment (which builds cache filenames from the same ticker)
  // is stricter -- a ticker with a space or an out-of-charset character passed this guard but
  // was silently never cached, triggering a live API call on every request with nothing
  // surfacing why.
  it('rejects a ticker containing characters the cache layer cannot safely use in a filename', async () => {
    const fastify = buildServer();

    const response = await fastify.inject({
      method: 'POST',
      url: '/api/valuate',
      payload: { ticker: 'AAPL/../ETC', exitPeMultiple: 15, requiredReturnPercent: 15, years: 10 },
    });

    expect(response.statusCode).toBe(400);
    const body = response.json();
    expect(body.ok).toBe(false);
    expect(body.error.type).toBe('INSUFFICIENT_DATA');
    expect(body.error.reason).toMatch(/ticker/i);
    expect(fetchStockData).not.toHaveBeenCalled();
  });

  // Regression: the frontend derived the bear/bull growth actually used from
  // lynch.bear.inputs/ruleOne.bear.inputs, which don't exist on a failed ValuationResult. When
  // ruleOne fails for a reason unrelated to growth (e.g. an emptied exit-P/E) while lynch
  // simultaneously fails for a *different* unrelated reason (this same growth being negative),
  // the real, known growth value was silently unrecoverable. The server must always echo back
  // the growth it actually used, independent of whether either method succeeded.
  it('echoes the actual bear/bull growth used even when both methods fail for that scenario', async () => {
    vi.mocked(fetchStockData).mockResolvedValue({
      ok: true,
      data: stockData({
        growth: {
          historical1yPercent: null,
          historical3yPercent: null,
          historical5yPercent: null,
          analystEstimate5yPercent: null,
        },
      }),
    });
    vi.mocked(fetchAnalystConsensus).mockResolvedValue({ ok: true, data: analystConsensus() });
    const fastify = buildServer();

    // bearGrowthRatePercent is an explicit -5 (negative -> trips lynch's NEGATIVE_GROWTH_RATE),
    // and bearExitPeMultiple is 0 (invalid -> trips ruleOne's INVALID_EXIT_PE) -- two unrelated
    // failures, neither of which carries the -5 growth in its (nonexistent, on failure) inputs.
    const response = await fastify.inject({
      method: 'POST',
      url: '/api/valuate',
      payload: {
        ticker: TICKER,
        growthRatePercent: 10,
        exitPeMultiple: 15,
        bearExitPeMultiple: 0,
        bearGrowthRatePercent: -5,
        requiredReturnPercent: 15,
        years: 10,
      },
    });

    const body = response.json();
    expect(body.ok).toBe(true);
    expect(body.ruleOne.bear.ok).toBe(false);
    expect(body.ruleOne.bear.error).toBe('INVALID_EXIT_PE');
    expect(body.lynch.bear.ok).toBe(false);
    expect(body.lynch.bear.error).toBe('NEGATIVE_GROWTH_RATE');
    // Both methods failed for unrelated reasons, but the server still reports the real growth.
    expect(body.bearGrowth).toBe(-5);
  });
});

describe('GET /api/history', () => {
  it('returns 200 with list of historical valuations', async () => {
    const mockData = [
      {
        id: '1',
        ticker: 'AAPL',
        evaluatedAt: '2026-08-19T10:00:00.000Z',
        currentPrice: 220,
        currency: 'USD',
        epsTtm: 6.5,
        growthRatePercent: 12,
        exitPeMultiple: 25,
        requiredReturnPercent: 15,
        years: 5,
        lynchFairValue: 156,
        ruleOneFairValue: 180,
      },
    ];
    vi.mocked(getHistory).mockResolvedValue({ ok: true, data: mockData });
    const fastify = buildServer();

    const response = await fastify.inject({
      method: 'GET',
      url: '/api/history?ticker=AAPL',
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.ok).toBe(true);
    expect(body.data).toEqual(mockData);
    expect(getHistory).toHaveBeenCalledWith('AAPL');
  });
});

describe('POST /api/history', () => {
  it('returns 201 when saving a valuation succeeds', async () => {
    const payload = {
      ticker: 'AAPL',
      currentPrice: 220,
      currency: 'USD',
      epsTtm: 6.5,
      growthRatePercent: 12,
      exitPeMultiple: 25,
      requiredReturnPercent: 15,
      years: 5,
      lynchFairValue: 156,
      ruleOneFairValue: 180,
    };
    const savedRecord = { ...payload, id: '123', evaluatedAt: '2026-08-19T10:00:00.000Z' };
    vi.mocked(saveValuation).mockResolvedValue({ ok: true, data: savedRecord });
    const fastify = buildServer();

    const response = await fastify.inject({
      method: 'POST',
      url: '/api/history',
      payload,
    });

    expect(response.statusCode).toBe(201);
    const body = response.json();
    expect(body.ok).toBe(true);
    expect(body.data).toEqual(savedRecord);
  });
});

describe('DELETE /api/history/:id', () => {
  it('returns 200 when deleting an existing valuation', async () => {
    const deletedRecord = {
      id: '123',
      ticker: 'AAPL',
      evaluatedAt: '2026-08-19T10:00:00.000Z',
      currentPrice: 220,
      currency: 'USD',
      epsTtm: 6.5,
      growthRatePercent: 12,
      exitPeMultiple: 25,
      requiredReturnPercent: 15,
      years: 5,
      lynchFairValue: 156,
      ruleOneFairValue: 180,
    };
    vi.mocked(deleteValuation).mockResolvedValue({ ok: true, data: deletedRecord });
    const fastify = buildServer();

    const response = await fastify.inject({
      method: 'DELETE',
      url: '/api/history/123',
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.ok).toBe(true);
    expect(body.data).toEqual(deletedRecord);
  });

  it('returns 404 when item to delete is not found', async () => {
    vi.mocked(deleteValuation).mockResolvedValue({
      ok: false,
      error: { type: 'NOT_FOUND', id: 'unknown' },
    });
    const fastify = buildServer();

    const response = await fastify.inject({
      method: 'DELETE',
      url: '/api/history/unknown',
    });

    expect(response.statusCode).toBe(404);
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
