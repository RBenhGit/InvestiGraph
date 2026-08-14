import { clampGrowthRate } from '../shared/clampGrowthRate';
import type { ValuationInputsUsed, ValuationResult } from '../shared/types';

export type RuleOneInputsUsed = ValuationInputsUsed & {
  exitPeMultiple: number;
  requiredReturnPercent: number;
  years: number;
};

/**
 * Method B (Rule #1-style): project EPS forward `years` at the (clamped) growth rate, apply an
 * exit P/E multiple, discount back at `requiredReturnPercent`. A single terminal-value multiple,
 * not a DCF with annual cash-flow projection.
 *
 * `epsTtm` and `growthRatePercent` are widened to accept `null`/`undefined` for the same reason
 * as `calculateLynchValue` — both flow in from independently-nullable `StockData` fields.
 */
export function calculateRuleOneValue(
  epsTtm: number | null | undefined,
  growthRatePercent: number | null | undefined,
  exitPeMultiple: number,
  requiredReturnPercent: number,
  years: number,
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

  const growthRatePercentClamped = clampGrowthRate(growthRatePercent);
  const g = growthRatePercentClamped / 100;
  const r = requiredReturnPercent / 100;
  const epsFuture = epsTtm * Math.pow(1 + g, years);
  const futurePrice = epsFuture * exitPeMultiple;
  const fairValue = futurePrice / Math.pow(1 + r, years);

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
    },
    intermediate: { epsFuture, futurePrice },
  };
}
