// Pure normalization/validation helpers for Twelve Data responses. No network calls, no
// imports from client.ts or env.ts — see task plan for the boundary rule.

/**
 * Parses an unknown API field into a number, treating a genuine `0` as a real value rather
 * than a missing one. A prior project shipped a P0 bug where falsy-zero fell through to a
 * fallback/null path — this function is the named regression guard against that.
 */
export function parseNumber(value: unknown): number | null {
  if (value === 0) return 0;
  if (value === null || value === undefined) return null;
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : null;
  }
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (trimmed === '') return null;
    const parsed = Number(trimmed);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

/**
 * Resolves trailing-twelve-month diluted EPS.
 *
 * Prefers the API's point-in-time EPS (though note that in production, `index.ts` currently passes `null`
 * to bypass this branch in favor of the income statement data), but treats exactly `0` the same as missing
 * (a real TTM EPS of precisely zero isn't a value to trust blindly). Falls back to
 * `netIncomeTtm / mean(dilutedSharesOutstanding)` derived from the last 4 quarters of
 * income-statement data — there is no direct "net income" parameter because diluted EPS ×
 * diluted shares for a quarter already approximates that quarter's net income, and summing
 * four quarters of that product gives TTM net income without a separate field.
 *
 * `quarterlyDilutedEps` and `quarterlyDilutedShares` are expected most-recent-first, one entry
 * per quarter. Fewer than 4 quarters in either array means the fallback can't be computed
 * without guessing from partial data, so this returns `null` rather than an estimate.
 */
export function resolveTtmEps(
  apiEps: number | null,
  quarterlyDilutedEps: number[],
  quarterlyDilutedShares: number[],
): number | null {
  if (apiEps !== null && apiEps !== 0 && Number.isFinite(apiEps)) {
    return apiEps;
  }

  if (quarterlyDilutedEps.length < 4 || quarterlyDilutedShares.length < 4) {
    return null;
  }

  const lastFourEps = quarterlyDilutedEps.slice(0, 4);
  const lastFourShares = quarterlyDilutedShares.slice(0, 4);

  const netIncomeTtm = lastFourEps.reduce(
    (sum, eps, i) => sum + eps * lastFourShares[i],
    0,
  );
  const meanShares = lastFourShares.reduce((sum, shares) => sum + shares, 0) / 4;

  if (meanShares === 0) return null;

  return netIncomeTtm / meanShares;
}

/** Thrown by `assertNonEmpty` when a 200 response doesn't actually carry usable data. */
export class TwelveDataResponseError extends Error {
  readonly type: 'EMPTY_RESPONSE' | 'API_ERROR' | 'RATE_LIMIT';
  readonly endpoint: string;
  readonly apiMessage?: string;

  constructor(type: 'EMPTY_RESPONSE' | 'API_ERROR' | 'RATE_LIMIT', endpoint: string, apiMessage?: string) {
    super(
      type === 'RATE_LIMIT'
        ? `Rate limit exceeded on Twelve Data endpoint ${endpoint}. Please wait a minute and try again.`
        : type === 'API_ERROR'
          ? `Twelve Data API error from ${endpoint}: ${apiMessage ?? 'unknown error'}`
          : `Empty response from Twelve Data endpoint ${endpoint}`,
    );
    this.name = 'TwelveDataResponseError';
    this.type = type;
    this.endpoint = endpoint;
    this.apiMessage = apiMessage;
  }
}

/**
 * Throws on `null`, `[]`, `{}`, or a Twelve Data `status: "error"` payload. A 200 status code
 * is not, by itself, evidence of valid data.
 */
export function assertNonEmpty(raw: unknown, endpoint: string): void {
  if (raw === null || raw === undefined) {
    throw new TwelveDataResponseError('EMPTY_RESPONSE', endpoint);
  }

  if (Array.isArray(raw)) {
    if (raw.length === 0) {
      throw new TwelveDataResponseError('EMPTY_RESPONSE', endpoint);
    }
    return;
  }

  if (typeof raw === 'object') {
    const obj = raw as Record<string, unknown>;
    if (obj.status === 'error') {
      const message = typeof obj.message === 'string' ? obj.message : undefined;
      if (message && message.toLowerCase().includes('limit')) {
        throw new TwelveDataResponseError('RATE_LIMIT', endpoint, message);
      }
      throw new TwelveDataResponseError('API_ERROR', endpoint, message);
    }
    if (Object.keys(obj).length === 0) {
      throw new TwelveDataResponseError('EMPTY_RESPONSE', endpoint);
    }
  }
}

/** Thrown by `validateCurrency` when price and fundamentals data disagree on currency unit. */
export class CurrencyMismatchError extends Error {
  readonly detail: string;

  constructor(priceCurrency: string, fundamentalsCurrency: string) {
    const detail = `price currency "${priceCurrency}" does not match fundamentals currency "${fundamentalsCurrency}"`;
    super(detail);
    this.name = 'CurrencyMismatchError';
    this.detail = detail;
  }
}

/** Validates that price and fundamentals data share one currency unit instead of guessing. */
export function validateCurrency(priceCurrency: string, fundamentalsCurrency: string): void {
  if (priceCurrency !== fundamentalsCurrency) {
    throw new CurrencyMismatchError(priceCurrency, fundamentalsCurrency);
  }
}

/**
 * CAGR is undefined (would require a complex root) when the earlier EPS was zero or negative —
 * a company that swung from a loss to a profit doesn't have a meaningful "growth rate" in this
 * formula. Returns `null` rather than a misleading number.
 *
 * The same is true in the other direction: a swing from profit to LOSS makes the ratio
 * negative, and `Math.pow(negative, 1/years)` is `NaN` for any `years > 1`. That must also
 * become `null`, not `NaN` — a `NaN` here is far worse than a missing value, because every
 * downstream consumer treats "not null" as "usable": the CLI's `!== null` fallback chain and
 * the server's `??` chain would both select the NaN and SHADOW a valid 1y CAGR sitting below
 * it, producing MISSING_GROWTH_RATE for a stock that had perfectly good growth data.
 * Absence is represented by `null` throughout this codebase; NaN must never escape.
 */
export function calculateCagrPercent(
  epsLatest: number | null,
  epsPast: number | null,
  years: number,
): number | null {
  if (epsLatest === null || epsPast === null) return null;
  if (epsPast <= 0) return null;
  // A zero/negative window would divide by zero in the exponent (Infinity/NaN).
  if (!(years > 0)) return null;
  const result = (Math.pow(epsLatest / epsPast, 1 / years) - 1) * 100;
  return Number.isFinite(result) ? result : null;
}
