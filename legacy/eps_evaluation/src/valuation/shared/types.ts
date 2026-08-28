export interface ValuationInputsUsed {
  epsTtm: number;
  growthRatePercentRaw: number;
  growthRatePercentClamped: number;
}

export type ValuationError =
  | 'MISSING_EPS'
  | 'NEGATIVE_OR_ZERO_EPS'
  | 'MISSING_GROWTH_RATE'
  // Lynch only: `EPS x growth%` is only meaningful for positive growth. A non-positive rate
  // yields a zero or NEGATIVE dollar figure, which is not a low valuation but a meaningless one.
  | 'NEGATIVE_GROWTH_RATE'
  | 'INVALID_EXIT_PE'
  | 'INVALID_REQUIRED_RETURN'
  | 'INVALID_YEARS'
  | 'INVALID_MOS';

export type ValuationResult<TInputs> =
  | { ok: true; fairValue: number; inputs: TInputs; intermediate?: Record<string, number> }
  | { ok: false; error: ValuationError };
