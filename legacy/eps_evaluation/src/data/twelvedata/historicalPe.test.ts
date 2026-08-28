import { describe, expect, it } from 'vitest';
import { computeHistoricalPeAverages } from './historicalPe';
import type { AnnualEpsPoint, MonthlyClosePoint } from './types';

/** `count` fiscal year-end dates, most-recent-first: 2025-12-31, 2024-12-31, ... */
function fiscalYearEndDates(count: number): string[] {
  const dates: string[] = [];
  for (let i = 0; i < count; i++) {
    dates.push(`${2025 - i}-12-31`);
  }
  return dates;
}

function makeAnnualEps(dilutedEpsValues: number[]): AnnualEpsPoint[] {
  const dates = fiscalYearEndDates(dilutedEpsValues.length);
  return dilutedEpsValues.map((dilutedEps, i) => ({ periodEnd: dates[i], dilutedEps }));
}

function makeMonthlyCloses(dates: string[], close: number): MonthlyClosePoint[] {
  return dates.map((date) => ({ date, close }));
}

describe('computeHistoricalPeAverages', () => {
  it('computes avg1y/avg3y/avg5y from a fixture with 6 years of constant EPS and price', () => {
    // Constant diluted EPS of 2/year, constant close of 20 => every annual P/E point is
    // 20/2 = 10, so every window's median is exactly 10.
    const annualEps = makeAnnualEps(new Array(6).fill(2));
    const monthlyCloses = makeMonthlyCloses(
      annualEps.map((p) => p.periodEnd),
      20,
    );

    const result = computeHistoricalPeAverages(annualEps, monthlyCloses);

    expect(result.avg1y).toBeCloseTo(10, 10);
    expect(result.avg3y).toBeCloseTo(10, 10);
    expect(result.avg5y).toBeCloseTo(10, 10);
  });

  it('takes the median (not mean) of the window, so one outlier year does not dominate', () => {
    // EPS=[1,2,2,2,2], close=[40,20,20,20,20] (most-recent-first) => P/E=[40,10,10,10,10].
    // Mean would be 16; median is 10.
    const annualEps = makeAnnualEps([1, 2, 2, 2, 2]);
    const monthlyCloses: MonthlyClosePoint[] = annualEps.map((p, i) => ({
      date: p.periodEnd,
      close: i === 0 ? 40 : 20,
    }));

    const result = computeHistoricalPeAverages(annualEps, monthlyCloses);

    expect(result.avg5y).toBeCloseTo(10, 10);
  });

  it('excludes a non-positive-EPS year from its window rather than nulling the whole window', () => {
    // 5 years of EPS: [2, -1, 2, 2, 2] => P/E points: [10, null, 10, 10, 10] (close=20 throughout).
    // avg5y window has 4 valid points (>= ceil(5/2)=3), median of [10,10,10,10] = 10.
    const annualEps = makeAnnualEps([2, -1, 2, 2, 2]);
    const monthlyCloses = makeMonthlyCloses(
      annualEps.map((p) => p.periodEnd),
      20,
    );

    const result = computeHistoricalPeAverages(annualEps, monthlyCloses);

    expect(result.avg5y).toBeCloseTo(10, 10);
  });

  it('nulls a window when too few valid points remain (below ceil(windowSize/2))', () => {
    // 3 years of EPS: [2, -1, -1] => P/E points: [10, null, null]. avg3y has 1 valid point,
    // short of ceil(3/2)=2, so avg3y is null. avg1y (window size 1) has its single point valid.
    const annualEps = makeAnnualEps([2, -1, -1]);
    const monthlyCloses = makeMonthlyCloses(
      annualEps.map((p) => p.periodEnd),
      20,
    );

    const result = computeHistoricalPeAverages(annualEps, monthlyCloses);

    expect(result.avg1y).toBeCloseTo(10, 10);
    expect(result.avg3y).toBeNull();
  });

  it('computes avg3y from partial history (2 of 3 points still meets ceil(3/2)=2) but leaves avg5y null', () => {
    // Only 2 years of history: avg3y's window has 2 valid points, meeting its ceil(3/2)=2
    // floor, so it still computes (median of [10,10]=10) even though the window isn't full.
    // avg5y's window has the same 2 valid points, short of its ceil(5/2)=3 floor, so it's null.
    const annualEps = makeAnnualEps([2, 2]);
    const monthlyCloses = makeMonthlyCloses(
      annualEps.map((p) => p.periodEnd),
      20,
    );

    const result = computeHistoricalPeAverages(annualEps, monthlyCloses);

    expect(result.avg1y).toBeCloseTo(10, 10);
    expect(result.avg3y).toBeCloseTo(10, 10);
    expect(result.avg5y).toBeNull();
  });

  it('matches a fiscal year-end with no exact month-end close to the nearest preceding one', () => {
    const annualEps = makeAnnualEps(new Array(2).fill(2));
    const [, y1] = annualEps.map((p) => p.periodEnd);

    // y0 (most recent fiscal year-end) has no exact month-end close: the fixture has a later
    // close (which must be skipped, being after the year-end) and a gap, so the nearest
    // PRECEDING close (24) must be picked instead of the nearer-but-future one (999).
    const monthlyCloses: MonthlyClosePoint[] = [
      { date: '2026-01-31', close: 999 }, // after y0 — must be skipped
      { date: '2025-11-30', close: 24 }, // nearest preceding close for y0
      { date: y1, close: 20 },
    ];

    const result = computeHistoricalPeAverages(annualEps, monthlyCloses);

    // y0 -> 24/2=12
    expect(result.avg1y).toBeCloseTo(12, 10);
  });
});
