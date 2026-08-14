import { describe, expect, it } from 'vitest';
import { computeHistoricalPeAverages } from './historicalPe';
import type { MonthlyClosePoint, QuarterlyEpsPoint } from './types';

/** Last day of `month0` (0-indexed) in `year`, as an ISO `YYYY-MM-DD` string. */
function monthEnd(year: number, month0: number): string {
  return new Date(Date.UTC(year, month0 + 1, 0)).toISOString().slice(0, 10);
}

/** `count` quarter-end dates, most-recent-first, stepping back 3 months at a time from
 * 2025-12-31 (a calendar quarter-end). */
function quarterEndDates(count: number): string[] {
  const dates: string[] = [];
  let year = 2025;
  let month0 = 11; // December
  for (let i = 0; i < count; i++) {
    dates.push(monthEnd(year, month0));
    month0 -= 3;
    if (month0 < 0) {
      month0 += 12;
      year -= 1;
    }
  }
  return dates;
}

function makeQuarterlyEps(dilutedEpsValues: number[]): QuarterlyEpsPoint[] {
  const dates = quarterEndDates(dilutedEpsValues.length);
  return dilutedEpsValues.map((dilutedEps, i) => ({ periodEnd: dates[i], dilutedEps }));
}

function makeMonthlyCloses(dates: string[], close: number): MonthlyClosePoint[] {
  return dates.map((date) => ({ date, close }));
}

describe('computeHistoricalPeAverages', () => {
  it('computes avg1y/avg3y/avg5y from a fixture with enough quarters for all windows', () => {
    // Constant diluted EPS of 1/quarter => ttmEps = 4 every point; constant close of 40 =>
    // every quarterly P/E point is 40/4 = 10, so every window average is exactly 10.
    // 23 quarters of EPS are needed to produce the 20 trailing P/E points avg5y requires,
    // since each P/E point consumes a quarter plus its 3 preceding quarters.
    const quarterlyEps = makeQuarterlyEps(new Array(23).fill(1));
    const monthlyCloses = makeMonthlyCloses(
      quarterlyEps.map((q) => q.periodEnd),
      40,
    );

    const result = computeHistoricalPeAverages(quarterlyEps, monthlyCloses);

    expect(result.avg1y).toBeCloseTo(10, 10);
    expect(result.avg3y).toBeCloseTo(10, 10);
    expect(result.avg5y).toBeCloseTo(10, 10);
  });

  it('nulls avg1y/avg3y/avg5y when a loss quarter falls inside the trailing-4 window', () => {
    // Same 23-quarter fixture, but the second-most-recent quarter is a large loss, which
    // drives the TTM EPS at the two most recent quarter-ends negative — poisoning the
    // trailing-4 window, and therefore (since windows are nested) the trailing-12 and
    // trailing-20 windows too.
    const epsValues = new Array(23).fill(1);
    epsValues[1] = -5;
    const quarterlyEps = makeQuarterlyEps(epsValues);
    const monthlyCloses = makeMonthlyCloses(
      quarterlyEps.map((q) => q.periodEnd),
      40,
    );

    const result = computeHistoricalPeAverages(quarterlyEps, monthlyCloses);

    expect(result.avg1y).toBeNull();
    expect(result.avg3y).toBeNull();
    expect(result.avg5y).toBeNull();
  });

  it('computes avg1y but leaves avg3y/avg5y null with only 8 quarters of history', () => {
    const quarterlyEps = makeQuarterlyEps(new Array(8).fill(1));
    const monthlyCloses = makeMonthlyCloses(
      quarterlyEps.map((q) => q.periodEnd),
      40,
    );

    const result = computeHistoricalPeAverages(quarterlyEps, monthlyCloses);

    expect(result.avg1y).toBeCloseTo(10, 10);
    expect(result.avg3y).toBeNull();
    expect(result.avg5y).toBeNull();
  });

  it('matches a quarter-end with no exact month-end close to the nearest preceding one', () => {
    // 7 quarters => exactly 4 computable trailing P/E points, so avg1y uses all of them.
    const quarterlyEps = makeQuarterlyEps(new Array(7).fill(1));
    const [, q1, q2, q3] = quarterlyEps.map((q) => q.periodEnd);

    // q0 (the most recent quarter-end) has no exact month-end close: the fixture has a
    // later close (which must be skipped, being after the quarter-end) and a gap, so the
    // nearest PRECEDING close (48) must be picked instead of the nearer-but-future one (999).
    const monthlyCloses: MonthlyClosePoint[] = [
      { date: monthEnd(2026, 0), close: 999 }, // 2026-01-31, after q0 — must be skipped
      { date: monthEnd(2025, 10), close: 48 }, // 2025-11-30, nearest preceding close for q0
      { date: q1, close: 40 },
      { date: q2, close: 40 },
      { date: q3, close: 40 },
    ];

    const result = computeHistoricalPeAverages(quarterlyEps, monthlyCloses);

    // Points: q0 -> 48/4=12, q1 -> 40/4=10, q2 -> 10, q3 -> 10. avg1y = (12+10+10+10)/4 = 10.5.
    expect(result.avg1y).toBeCloseTo(10.5, 10);
  });
});
