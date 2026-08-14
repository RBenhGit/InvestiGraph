import { clampGrowthRate } from '../shared/clampGrowthRate';
import type { ValuationInputsUsed, ValuationResult } from '../shared/types';

/**
 * Method A (Lynch/PEG-style): `FairValue = EPS_ttm * growthRatePercent`, no discounting.
 *
 * `epsTtm` and `growthRatePercent` are widened to accept `null`/`undefined` because they flow
 * in directly from `StockData` fields (e.g. `growth.analystEstimate5yPercent`) that are
 * independently nullable — this function is what turns that absence into `MISSING_EPS` /
 * `MISSING_GROWTH_RATE` rather than pushing a non-null assertion onto every caller.
 */
export function calculateLynchValue(
  epsTtm: number | null | undefined,
  growthRatePercent: number | null | undefined,
): ValuationResult<ValuationInputsUsed> {
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

  const growthRatePercentClamped = clampGrowthRate(growthRatePercent);
  const fairValue = epsTtm * growthRatePercentClamped;

  return {
    ok: true,
    fairValue,
    inputs: {
      epsTtm,
      growthRatePercentRaw: growthRatePercent,
      growthRatePercentClamped,
    },
  };
}
