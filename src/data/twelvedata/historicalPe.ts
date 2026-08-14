// Pure computation of trailing average P/E ratios from locally-held quarterly EPS and monthly
// close data. No network calls — see task plan for the boundary rule.

import type { HistoricalPeAverages, MonthlyClosePoint, QuarterlyEpsPoint } from './types';

/** Nearest month-end close at or before `quarterEndDate` (both are ISO `YYYY-MM-DD` strings,
 * so lexical comparison is date comparison). `monthlyCloses` is most-recent-first, so the
 * first match walking forward is the nearest preceding close. */
function nearestPrecedingClose(
  quarterEndDate: string,
  monthlyCloses: MonthlyClosePoint[],
): number | null {
  for (const point of monthlyCloses) {
    if (point.date <= quarterEndDate) {
      return point.close;
    }
  }
  return null;
}

/**
 * One quarterly P/E point per computable quarter-end (most recent first). A quarter-end at
 * index `i` needs itself plus the 3 preceding (older, i.e. higher-index) quarters to form a
 * TTM EPS, so the last 3 entries of `quarterlyEps` never produce a point. `null` marks a point
 * that couldn't be computed (non-positive TTM EPS, or no preceding close available) — callers
 * must not average past a `null`.
 */
function computeQuarterlyPePoints(
  quarterlyEps: QuarterlyEpsPoint[],
  monthlyCloses: MonthlyClosePoint[],
): Array<number | null> {
  const points: Array<number | null> = [];
  for (let i = 0; i + 3 < quarterlyEps.length; i++) {
    const ttmEps =
      quarterlyEps[i].dilutedEps +
      quarterlyEps[i + 1].dilutedEps +
      quarterlyEps[i + 2].dilutedEps +
      quarterlyEps[i + 3].dilutedEps;

    if (ttmEps <= 0) {
      points.push(null);
      continue;
    }

    const close = nearestPrecedingClose(quarterlyEps[i].periodEnd, monthlyCloses);
    points.push(close === null ? null : close / ttmEps);
  }
  return points;
}

/** All-or-nothing mean over the `windowSize` most recent points: `null` if there aren't enough
 * points yet, or if any point in the window is `null` (one loss quarter poisons the window). */
function averageWindow(points: Array<number | null>, windowSize: number): number | null {
  if (points.length < windowSize) return null;
  const window = points.slice(0, windowSize);
  if (window.some((p) => p === null)) return null;
  const sum = (window as number[]).reduce((acc, p) => acc + p, 0);
  return sum / windowSize;
}

export function computeHistoricalPeAverages(
  quarterlyEps: QuarterlyEpsPoint[],
  monthlyCloses: MonthlyClosePoint[],
): HistoricalPeAverages {
  const points = computeQuarterlyPePoints(quarterlyEps, monthlyCloses);
  return {
    avg1y: averageWindow(points, 4),
    avg3y: averageWindow(points, 12),
    avg5y: averageWindow(points, 20),
  };
}
