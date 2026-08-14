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

  it('clamps growth=40 to 25, proving the clamp actually fires', () => {
    const result = calculateLynchValue(5, 40);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.fairValue).toBe(125);
      expect(result.inputs.growthRatePercentClamped).toBe(25);
      expect(result.inputs.growthRatePercentRaw).toBe(40);
    }
  });
});
