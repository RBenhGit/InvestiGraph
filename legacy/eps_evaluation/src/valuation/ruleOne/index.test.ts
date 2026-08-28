import { describe, expect, it } from 'vitest';
import { calculateRuleOneValue } from './index';

describe('calculateRuleOneValue', () => {
  it('collapses to eps * exitPe when growth equals required return ((1+g)^N cancels (1+r)^N)', () => {
    const result = calculateRuleOneValue(10, 10, 15, 10, 10);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.fairValue).toBeCloseTo(150, 6);
    }
  });

  it('discounts away from the naive eps * exitPe when growth != required return', () => {
    const result = calculateRuleOneValue(10, 15, 15, 10, 10);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.fairValue).not.toBeCloseTo(150, 0);
      expect(result.fairValue).toBeCloseTo(233.96064555028698, 6);
    }
  });

  it('returns MISSING_EPS when eps is missing', () => {
    const result = calculateRuleOneValue(null, 10, 15, 10, 10);
    expect(result).toEqual({ ok: false, error: 'MISSING_EPS' });
  });

  it('returns NEGATIVE_OR_ZERO_EPS when eps <= 0', () => {
    const result = calculateRuleOneValue(0, 10, 15, 10, 10);
    expect(result).toEqual({ ok: false, error: 'NEGATIVE_OR_ZERO_EPS' });
  });

  it('returns MISSING_GROWTH_RATE when growth is missing', () => {
    const result = calculateRuleOneValue(10, null, 15, 10, 10);
    expect(result).toEqual({ ok: false, error: 'MISSING_GROWTH_RATE' });
  });

  it('returns INVALID_EXIT_PE when exitPeMultiple is not positive', () => {
    const result = calculateRuleOneValue(10, 10, 0, 10, 10);
    expect(result).toEqual({ ok: false, error: 'INVALID_EXIT_PE' });
  });

  it('returns INVALID_REQUIRED_RETURN when requiredReturnPercent is not positive', () => {
    const result = calculateRuleOneValue(10, 10, 15, 0, 10);
    expect(result).toEqual({ ok: false, error: 'INVALID_REQUIRED_RETURN' });
  });

  it('returns INVALID_YEARS when years is not a positive integer', () => {
    const result = calculateRuleOneValue(10, 10, 15, 10, 0);
    expect(result).toEqual({ ok: false, error: 'INVALID_YEARS' });
  });

  it('applies margin of safety discount correctly when mosPercent > 0', () => {
    // With g = 10, r = 10, sticker price is 150.
    // With 25% MoS, fairValue should be 150 * 0.75 = 112.5
    const result = calculateRuleOneValue(10, 10, 15, 10, 10, 25);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.fairValue).toBeCloseTo(112.5, 6);
      expect(result.inputs.mosPercent).toBe(25);
      expect(result.intermediate?.stickerPrice).toBeCloseTo(150, 6);
      expect(result.intermediate?.mosPrice).toBeCloseTo(112.5, 6);
    }
  });

  it('returns INVALID_MOS when mosPercent is negative or >= 100', () => {
    expect(calculateRuleOneValue(10, 10, 15, 10, 10, -5)).toEqual({
      ok: false,
      error: 'INVALID_MOS',
    });
    expect(calculateRuleOneValue(10, 10, 15, 10, 10, 100)).toEqual({
      ok: false,
      error: 'INVALID_MOS',
    });
  });
});
