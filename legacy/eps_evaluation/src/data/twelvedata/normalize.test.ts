import { describe, expect, it } from 'vitest';
import {
  assertNonEmpty,
  calculateCagrPercent,
  calculateTtmEpsGrowthPercent,
  parseNumber,
  resolveTtmEps,
  TwelveDataResponseError,
  validateCurrency,
  CurrencyMismatchError,
} from './normalize';

describe('parseNumber', () => {
  it('returns 0 for input 0 (never falls through to null for a genuine zero)', () => {
    expect(parseNumber(0)).toBe(0);
  });

  it('returns null for null and undefined', () => {
    expect(parseNumber(null)).toBeNull();
    expect(parseNumber(undefined)).toBeNull();
  });

  it('parses numeric strings', () => {
    expect(parseNumber('3.5')).toBe(3.5);
  });

  it('returns null for non-numeric input', () => {
    expect(parseNumber('not-a-number')).toBeNull();
    expect(parseNumber({})).toBeNull();
    expect(parseNumber(NaN)).toBeNull();
  });
});

describe('resolveTtmEps', () => {
  it('computes correctly from exactly 4 quarters when API EPS is unavailable', () => {
    // Each quarter: eps=1, shares=100 => net income 100/quarter, TTM net income 400,
    // mean shares 100 => ttmEps = 4.
    const result = resolveTtmEps(null, [1, 1, 1, 1], [100, 100, 100, 100]);
    expect(result).toBe(4);
  });

  it('returns null with only 3 quarters of data (no partial estimates)', () => {
    const result = resolveTtmEps(null, [1, 1, 1], [100, 100, 100]);
    expect(result).toBeNull();
  });

  it('uses nonzero API EPS directly without touching the quarterly fallback path', () => {
    // Fallback data below would compute to a very different ttmEps (400/100=4) if used,
    // proving the API value (5) won when it is returned unchanged.
    const result = resolveTtmEps(5, [1, 1, 1, 1], [100, 100, 100, 100]);
    expect(result).toBe(5);
  });

  it('treats API EPS of exactly 0 as missing and falls back to quarterly data', () => {
    const result = resolveTtmEps(0, [1, 1, 1, 1], [100, 100, 100, 100]);
    expect(result).toBe(4);
  });
});

describe('calculateTtmEpsGrowthPercent', () => {
  it('computes true YoY TTM growth from 8 quarters (current 4 vs. year-ago 4)', () => {
    // Quarters 0-3 (current TTM): eps=3 each, shares=100 => TTM net income 1200, mean shares
    // 100 => ttmNow = 12. Quarters 4-7 (year-ago TTM): eps=2 each => ttmYearAgo = 8.
    // Growth = 12/8 - 1 = 50%.
    const eps = [3, 3, 3, 3, 2, 2, 2, 2];
    const shares = [100, 100, 100, 100, 100, 100, 100, 100];
    expect(calculateTtmEpsGrowthPercent(eps, shares)).toBeCloseTo(50, 10);
  });

  it('returns null with fewer than 8 quarters — never approximates from a shorter window', () => {
    // 6 quarters is exactly this plan tier's real-world ceiling (Twelve Data caps
    // income_statement quarterly at 6) — the case this guard exists for.
    const eps = [3, 3, 3, 3, 2, 2];
    const shares = [100, 100, 100, 100, 100, 100];
    expect(calculateTtmEpsGrowthPercent(eps, shares)).toBeNull();
  });

  it('returns null when the year-ago TTM window is zero or negative', () => {
    // A company with a genuine year-ago loss doesn't have a meaningful "growth rate" here,
    // same reasoning as calculateCagrPercent's epsPast <= 0 guard above.
    const eps = [3, 3, 3, 3, -1, -1, -1, -1];
    const shares = [100, 100, 100, 100, 100, 100, 100, 100];
    expect(calculateTtmEpsGrowthPercent(eps, shares)).toBeNull();
  });

  it('returns null when shares data is missing entries relative to eps', () => {
    const eps = [3, 3, 3, 3, 2, 2, 2, 2];
    const shares = [100, 100, 100, 100, 100, 100, 100]; // only 7
    expect(calculateTtmEpsGrowthPercent(eps, shares)).toBeNull();
  });
});

describe('assertNonEmpty', () => {
  it('throws on an empty object', () => {
    expect(() => assertNonEmpty({}, 'statistics')).toThrow(TwelveDataResponseError);
  });

  it('throws on an empty array', () => {
    expect(() => assertNonEmpty([], 'income_statement')).toThrow(TwelveDataResponseError);
  });

  it('throws on a status:"error" payload', () => {
    expect(() =>
      assertNonEmpty({ status: 'error', message: 'symbol not found' }, 'quote'),
    ).toThrow(TwelveDataResponseError);
  });

  it('throws on null', () => {
    expect(() => assertNonEmpty(null, 'quote')).toThrow(TwelveDataResponseError);
  });

  it('does not throw on a non-empty, non-error payload', () => {
    expect(() => assertNonEmpty({ symbol: 'AAPL' }, 'quote')).not.toThrow();
  });
});

describe('validateCurrency', () => {
  it('throws when currencies mismatch', () => {
    expect(() => validateCurrency('USD', 'EUR')).toThrow(CurrencyMismatchError);
  });

  it('does not throw when currencies match', () => {
    expect(() => validateCurrency('USD', 'USD')).not.toThrow();
  });
});

describe('calculateCagrPercent', () => {
  it('computes exactly 10% for eps 1.00 -> 1.331 over 3 years', () => {
    expect(calculateCagrPercent(1.331, 1.0, 3)).toBeCloseTo(10, 10);
  });

  it('returns null when epsPast <= 0 (a prior-year loss)', () => {
    expect(calculateCagrPercent(1.0, 0, 3)).toBeNull();
    expect(calculateCagrPercent(1.0, -0.5, 3)).toBeNull();
  });

  it('returns null when either value is missing', () => {
    expect(calculateCagrPercent(null, 1.0, 3)).toBeNull();
    expect(calculateCagrPercent(1.0, null, 3)).toBeNull();
  });

  // Regression: a company that swung from profit to loss gives epsLatest < 0 with epsPast > 0,
  // which passes the epsPast guard but makes Math.pow(negative, 1/years) return NaN for any
  // years > 1. That NaN then leaked into StockData.growth, where both the CLI's
  // `!== null` fallback chain and the server's `??` chain treat it as a usable value -- so it
  // SHADOWED a perfectly good 1y CAGR further down the chain, and the valuation came back
  // MISSING_GROWTH_RATE even though real growth data was available. Absence must be null.
  it('returns null (never NaN) when the latest EPS is negative', () => {
    expect(calculateCagrPercent(-2, 5, 3)).toBeNull();
    expect(calculateCagrPercent(-0.01, 1, 5)).toBeNull();
  });

  it('still computes a real -100% for a swing to exactly zero EPS', () => {
    // 0 is a legitimate endpoint: the value fell to nothing, i.e. -100%, not "unknown".
    expect(calculateCagrPercent(0, 5, 3)).toBeCloseTo(-100, 10);
  });

  it('returns null rather than Infinity for a non-positive years window', () => {
    expect(calculateCagrPercent(10, 5, 0)).toBeNull();
    expect(calculateCagrPercent(10, 5, -3)).toBeNull();
  });
});
