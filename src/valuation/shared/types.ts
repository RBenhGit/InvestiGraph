export interface ValuationInputsUsed {
  epsTtm: number;
  growthRatePercentRaw: number;
  growthRatePercentClamped: number;
}

export type ValuationError =
  | 'MISSING_EPS'
  | 'NEGATIVE_OR_ZERO_EPS'
  | 'MISSING_GROWTH_RATE'
  | 'INVALID_EXIT_PE'
  | 'INVALID_REQUIRED_RETURN'
  | 'INVALID_YEARS';

export type ValuationResult<TInputs> =
  | { ok: true; fairValue: number; inputs: TInputs; intermediate?: Record<string, number> }
  | { ok: false; error: ValuationError };
