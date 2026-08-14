import { describe, expect, it } from 'vitest';
import {
  clampGrowthRate,
  GROWTH_RATE_CAP_PERCENT,
  GROWTH_RATE_FLOOR_PERCENT,
} from './clampGrowthRate';

describe('clampGrowthRate', () => {
  it('leaves a value inside the band unchanged', () => {
    expect(clampGrowthRate(10)).toBe(10);
  });

  it('floors a value below the floor', () => {
    expect(clampGrowthRate(-20)).toBe(GROWTH_RATE_FLOOR_PERCENT);
  });

  it('caps a value above the cap', () => {
    expect(clampGrowthRate(40)).toBe(GROWTH_RATE_CAP_PERCENT);
  });

  it('leaves the exact floor boundary unchanged', () => {
    expect(clampGrowthRate(GROWTH_RATE_FLOOR_PERCENT)).toBe(GROWTH_RATE_FLOOR_PERCENT);
  });

  it('leaves the exact cap boundary unchanged', () => {
    expect(clampGrowthRate(GROWTH_RATE_CAP_PERCENT)).toBe(GROWTH_RATE_CAP_PERCENT);
  });
});
