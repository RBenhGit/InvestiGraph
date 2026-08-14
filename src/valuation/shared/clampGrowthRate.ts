/** Growth-rate clamp band applied before any valuation formula uses a growth rate. */
export const GROWTH_RATE_FLOOR_PERCENT = -5;
export const GROWTH_RATE_CAP_PERCENT = 25;

/** Clamps a raw growth-rate percentage into the sane band used by all valuation formulas. */
export function clampGrowthRate(g: number): number {
  return Math.min(GROWTH_RATE_CAP_PERCENT, Math.max(GROWTH_RATE_FLOOR_PERCENT, g));
}
