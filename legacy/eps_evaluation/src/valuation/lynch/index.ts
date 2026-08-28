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

  // `EPS x growth%` is a PEG-style heuristic defined only for a growing company. With a
  // non-positive rate it returns 0 or a negative dollar amount -- e.g. ABBV's real -29.03% 3y
  // CAGR (clamped to -5%) gave a "fair value" of -17.69, which the CLI and the web UI both
  // rendered as a legitimate number with a -108% "downside". That is not a cheap stock, it is
  // an inapplicable formula, so it must surface as an error. Rule #1 is unaffected: compounding
  // a positive EPS at a negative rate shrinks it without flipping the sign.
  if (growthRatePercent <= 0) {
    return { ok: false, error: 'NEGATIVE_GROWTH_RATE' };
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
