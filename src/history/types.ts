export interface ScenarioValuation {
  growthRatePercent: number | null;
  exitPeMultiple: number;
  requiredReturnPercent: number;
  mosPercent: number;
  lynchFairValue: number | null;
  ruleOneFairValue: number | null;
}

export interface SavedValuation {
  id: string;
  ticker: string;
  evaluatedAt: string; // ISO 8601 string, e.g. "2026-08-19T18:45:00.000Z"
  currentPrice: number;
  currency: string;
  epsTtm: number;
  epsOverride?: number;
  years: number;
  
  // Legacy fields (optional for backward compatibility)
  growthRatePercent?: number | null;
  exitPeMultiple?: number;
  requiredReturnPercent?: number;
  mosPercent?: number;
  lynchFairValue?: number | null;
  ruleOneFairValue?: number | null;

  // New fields
  base?: ScenarioValuation;
  bear?: ScenarioValuation;
  bull?: ScenarioValuation;

  notes?: string;
}

export type SaveValuationInput = Omit<SavedValuation, 'id' | 'evaluatedAt'> & {
  id?: string;
  evaluatedAt?: string;
};

export type HistoryError =
  | { type: 'IO_ERROR'; message: string }
  | { type: 'NOT_FOUND'; id: string }
  | { type: 'INVALID_INPUT'; reason: string };

export type HistoryResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: HistoryError };
