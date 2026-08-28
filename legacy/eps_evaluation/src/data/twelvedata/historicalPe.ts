// Pure computation of trailing median P/E ratios from locally-held annual EPS and monthly
// close data. No network calls — see task plan for the boundary rule.
//
// Annual, not quarterly: Twelve Data's `income_statement` endpoint caps `period=quarterly` at
// 6 quarters on this plan tier (see fetchQuarterlyIncomeStatement's comment in client.ts) — not
// enough for even a 1y trailing-P/E window under a quarterly TTM scheme. Annual EPS has no such
// cap (up to 6 fiscal years), so one P/E point per fiscal year is the only window that can ever
// be non-null here. Median, not mean: with as few as 1–5 points per window, one outlier year
// (e.g. a temporarily depressed EPS) would dominate a mean; the median is far less sensitive to
// that, at the cost of no longer being a literal "average". Ported from the equivalent
// annual/median approach in the EvalApp sibling project.

import type { AnnualEpsPoint, HistoricalPeAverages, MonthlyClosePoint } from './types';

/** Nearest month-end close at or before `fiscalYearEnd` (both are ISO `YYYY-MM-DD` strings, so
 * lexical comparison is date comparison). `monthlyCloses` is most-recent-first, so the first
 * match walking forward is the nearest preceding close. */
function nearestPrecedingClose(
  fiscalYearEnd: string,
  monthlyCloses: MonthlyClosePoint[],
): number | null {
  for (const point of monthlyCloses) {
    if (point.date <= fiscalYearEnd) {
      return point.close;
    }
  }
  return null;
}

/** One P/E point per fiscal year (most recent first): that year's diluted EPS paired with the
 * closest-preceding month-end close. `null` marks a year that can't produce a meaningful P/E
 * (non-positive EPS, or no preceding close available) — callers filter these out rather than
 * letting one bad year poison a whole window, per the median's ceil(N/2)-valid-points rule. */
function computeAnnualPePoints(
  annualEps: AnnualEpsPoint[],
  monthlyCloses: MonthlyClosePoint[],
): Array<number | null> {
  return annualEps.map((point) => {
    if (point.dilutedEps <= 0) return null;
    const close = nearestPrecedingClose(point.periodEnd, monthlyCloses);
    return close === null ? null : close / point.dilutedEps;
  });
}

/** Median of the valid points among the `windowSize` most recent annual P/E points. Unlike an
 * all-or-nothing mean, a single non-positive-EPS year doesn't null out the whole window — but
 * the window still needs at least half its points (rounded up) to be meaningful at all. */
function medianWindow(points: Array<number | null>, windowSize: number): number | null {
  const window = points.slice(0, windowSize);
  const valid = window.filter((p): p is number => p !== null);
  if (valid.length === 0) return null;
  if (valid.length < Math.ceil(windowSize / 2)) return null;

  const sorted = [...valid].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 1 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

export function computeHistoricalPeAverages(
  annualEps: AnnualEpsPoint[],
  monthlyCloses: MonthlyClosePoint[],
): HistoricalPeAverages {
  const points = computeAnnualPePoints(annualEps, monthlyCloses);
  return {
    avg1y: medianWindow(points, 1),
    avg3y: medianWindow(points, 3),
    avg5y: medianWindow(points, 5),
  };
}
