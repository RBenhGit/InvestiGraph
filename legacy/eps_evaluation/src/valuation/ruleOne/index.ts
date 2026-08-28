import { clampGrowthRate } from '../shared/clampGrowthRate';
import type { ValuationInputsUsed, ValuationResult } from '../shared/types';

export type RuleOneInputsUsed = ValuationInputsUsed & {
  exitPeMultiple: number;
  requiredReturnPercent: number;
  years: number;
  mosPercent: number;
};

/**
 * Method B (Rule #1-style): project EPS forward `years` at the (clamped) growth rate, apply an
 * exit P/E multiple, discount back at `requiredReturnPercent`.
 *
 * An optional `mosPercent` (Margin of Safety, e.g. 25 for 25%, defaults to 0) discounts the sticker price
 * down to the target buy price (fairValue = stickerPrice * (1 - mosPercent / 100)).
 */
export function calculateRuleOneValue(
  epsTtm: number | null | undefined,
  growthRatePercent: number | null | undefined,
  exitPeMultiple: number,
  requiredReturnPercent: number,
  years: number,
  mosPercent: number = 0,
): ValuationResult<RuleOneInputsUsed> {
  if (epsTtm === null || epsTtm === undefined || Number.isNaN(epsTtm)) {
    return { ok: false, error: 'MISSING_EPS' };
  }
  if (epsTtm <= 0) {
    return { ok: false, error: 'NEGATIVE_OR_ZERO_EPS' };
  }
  if (
    growthRatePercent === null ||
    growthRatePercent === undefined ||
    Number.isNaN(growthRatePercent)
  ) {
    return { ok: false, error: 'MISSING_GROWTH_RATE' };
  }
  if (!(exitPeMultiple > 0)) {
    return { ok: false, error: 'INVALID_EXIT_PE' };
  }
  if (!(requiredReturnPercent > 0)) {
    return { ok: false, error: 'INVALID_REQUIRED_RETURN' };
  }
  if (!Number.isInteger(years) || years <= 0) {
    return { ok: false, error: 'INVALID_YEARS' };
  }
  if (Number.isNaN(mosPercent) || mosPercent < 0 || mosPercent >= 100) {
    return { ok: false, error: 'INVALID_MOS' };
  }

  const growthRatePercentClamped = clampGrowthRate(growthRatePercent);
  const g = growthRatePercentClamped / 100;
  const r = requiredReturnPercent / 100;
  const epsFuture = epsTtm * Math.pow(1 + g, years);
  const futurePrice = epsFuture * exitPeMultiple;
  const stickerPrice = futurePrice / Math.pow(1 + r, years);
  const fairValue = mosPercent > 0 ? stickerPrice * (1 - mosPercent / 100) : stickerPrice;

  return {
    ok: true,
    fairValue,
    inputs: {
      epsTtm,
      growthRatePercentRaw: growthRatePercent,
      growthRatePercentClamped,
      exitPeMultiple,
      requiredReturnPercent,
      years,
      mosPercent,
    },
    intermediate: { epsFuture, futurePrice, stickerPrice, mosPrice: fairValue },
  };
}
