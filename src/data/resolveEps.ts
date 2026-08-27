// Shared sibling of twelvedata/ and yahoo/ (same pattern as cache.ts) — reconciles
// StockData.epsTtm against Yahoo's independent trailingEps when Twelve Data's own
// staleTtmWarning flags a likely-stale quarter. Both adapters (cli/index.ts, server.ts) call
// this the same way so their behavior can't diverge — see CLAUDE.md's warning about the growth
// fallback chain drifting between adapters in the past.
import type { StockData } from './twelvedata/types';
import type { AnalystConsensus } from './yahoo/types';

export type EpsSource =
  | 'twelvedata' // no staleness concern — used as-is
  | 'yahoo-fallback' // Twelve Data looked stale; Yahoo's trailingEps was available and used instead
  | 'twelvedata-stale-no-fallback'; // Twelve Data looked stale; Yahoo was unavailable/failed, kept the stale value

export interface ResolvedEps {
  epsTtm: number;
  source: EpsSource;
  // Human-readable note on the concrete asOf/quarter dates of whichever figure was used,
  // for CLI/web display — never invented, always derived from the actual data present.
  detail: string;
}

/**
 * Resolves the epsTtm actually shown to the user, given `StockData.staleTtmWarning` and an
 * independently-fetched (and independently-nullable, itself possibly failed) Yahoo
 * AnalystConsensus. Yahoo's trailingEps is a summed TTM figure, not decomposable into
 * quarters — so this is a whole-figure replacement, not a per-quarter splice. Only fires when
 * staleTtmWarning is true; a healthy Twelve Data figure is never second-guessed.
 */
export function resolveEpsWithFallback(
  data: StockData,
  analystConsensus: AnalystConsensus | null,
): ResolvedEps {
  if (!data.staleTtmWarning) {
    return {
      epsTtm: data.epsTtm,
      source: 'twelvedata',
      detail: `Twelve Data, as of ${data.asOf}`,
    };
  }

  const yahooEps = analystConsensus?.trailingEps;
  if (typeof yahooEps === 'number' && Number.isFinite(yahooEps) && yahooEps > 0) {
    const quarterNote = analystConsensus?.mostRecentQuarterEndDate
      ? ` (most recent quarter: ${analystConsensus.mostRecentQuarterEndDate})`
      : '';
    return {
      epsTtm: yahooEps,
      source: 'yahoo-fallback',
      detail: `Yahoo Finance, as of ${analystConsensus?.asOf}${quarterNote} — used because Twelve Data's figure ($${data.epsTtm.toFixed(2)}) looked stale`,
    };
  }

  return {
    epsTtm: data.epsTtm,
    source: 'twelvedata-stale-no-fallback',
    detail: `Twelve Data, as of ${data.asOf} — flagged as possibly stale, but Yahoo Finance was unavailable to cross-check`,
  };
}
