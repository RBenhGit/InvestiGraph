import { describe, expect, it } from 'vitest';
import { calculateLynchValue } from './index';

describe('calculateLynchValue', () => {
  it('computes fairValue = eps * growth', () => {
    const result = calculateLynchValue(5, 15);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.fairValue).toBe(75);
    }
  });

  it('returns NEGATIVE_OR_ZERO_EPS for eps=0', () => {
    const result = calculateLynchValue(0, 15);
    expect(result).toEqual({ ok: false, error: 'NEGATIVE_OR_ZERO_EPS' });
  });

  it('returns NEGATIVE_OR_ZERO_EPS for eps=-2', () => {
    const result = calculateLynchValue(-2, 15);
    expect(result).toEqual({ ok: false, error: 'NEGATIVE_OR_ZERO_EPS' });
  });

  it('returns MISSING_GROWTH_RATE when growth is missing', () => {
    const result = calculateLynchValue(5, null);
    expect(result).toEqual({ ok: false, error: 'MISSING_GROWTH_RATE' });
  });

  it('returns MISSING_EPS when eps is missing', () => {
    const result = calculateLynchValue(null, 15);
    expect(result).toEqual({ ok: false, error: 'MISSING_EPS' });
  });

  it('does not clamp high growth=40, proving there is no maximum ceiling', () => {
    const result = calculateLynchValue(5, 40);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.fairValue).toBe(200);
      expect(result.inputs.growthRatePercentClamped).toBe(40);
      expect(result.inputs.growthRatePercentRaw).toBe(40);
    }
  });

  // Regression, found by running the two methods over 26 real cached tickers: ABBV has a
  // genuinely negative 3y EPS CAGR (-29.03%, clamped to -5%), and `eps * growthPercent` then
  // produced a fair value of -17.69 -- a NEGATIVE DOLLAR AMOUNT returned as ok:true, which both
  // the CLI and the web UI rendered as a real valuation ("Method A (Lynch) fair value: -17.69",
  // and a -108.85% "downside" in the price banner). The Lynch/PEG heuristic is only defined for
  // positive growth; a shrinking company has no meaningful PEG fair value, so this is an error,
  // not a small number. Rule #1 is unaffected -- compounding a positive EPS at a negative rate
  // shrinks it without ever flipping the sign (ABBV still yields a sane 7.86 there).
  it('returns NEGATIVE_GROWTH_RATE instead of a negative dollar fair value', () => {
    const result = calculateLynchValue(3.538947, -29.0294);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toBe('NEGATIVE_GROWTH_RATE');
  });

  it('also rejects a growth rate of exactly zero, which would value the company at $0', () => {
    const result = calculateLynchValue(5, 0);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toBe('NEGATIVE_GROWTH_RATE');
  });

  it('still values a normally-growing company', () => {
    const result = calculateLynchValue(5, 12);
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.fairValue).toBeCloseTo(60, 10);
  });
});
