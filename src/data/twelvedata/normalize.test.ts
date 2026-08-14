import { describe, expect, it } from 'vitest';
import {
  assertNonEmpty,
  calculateCagrPercent,
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
});
