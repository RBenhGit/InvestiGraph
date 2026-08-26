import { describe, expect, it, beforeEach, afterEach } from 'vitest';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {
  saveCachedStockData,
  getCachedStockData,
  saveCachedYahooData,
  getCachedYahooData,
} from './cache';
import type { StockData } from './twelvedata/types';
import type { AnalystConsensus } from './yahoo/types';

describe('cache layer', () => {
  let tempDir: string;

  beforeEach(async () => {
    tempDir = await fs.mkdtemp(path.join(os.tmpdir(), 'cache-test-'));
  });

  afterEach(async () => {
    await fs.rm(tempDir, { recursive: true, force: true }).catch(() => {});
  });

  // Regression: `ticker` was interpolated straight into path.join() with no sanitisation, so a
  // traversal sequence escaped the cache directory entirely -- path.join(dir,
  // 'twelvedata_' + 'A/../../B' + '.json') resolves ABOVE dir. getCachedStockData is called
  // before any network request in fetchStockData, so an attacker-controlled ticker reaches this
  // read path on every lookup. A ticker is [A-Z0-9.:-] in practice; anything else is not a
  // ticker and must not become a filesystem path.
  it('refuses a traversal ticker instead of reading outside the cache directory', async () => {
    const outsideDir = path.dirname(tempDir);
    const plantedPath = path.join(outsideDir, 'PWNED.json');
    await fs.writeFile(plantedPath, JSON.stringify({ ticker: 'PWNED', epsTtm: 1 }), 'utf8');

    try {
      const result = await getCachedStockData('twelvedata_x/../../PWNED', tempDir);
      expect(result).toBeNull();

      const yahooResult = await getCachedYahooData('yahoo_x/../../PWNED', tempDir);
      expect(yahooResult).toBeNull();
    } finally {
      await fs.rm(plantedPath, { force: true }).catch(() => {});
    }
  });

  it('refuses to write a cache file outside the cache directory', async () => {
    const outsideDir = path.dirname(tempDir);
    const escapeName = path.basename(tempDir) + '/../ESCAPED';
    const escapedPath = path.join(outsideDir, 'twelvedata_ESCAPED.json');

    try {
      await saveCachedStockData(
        escapeName,
        { ticker: 'X', epsTtm: 1 } as unknown as StockData,
        tempDir,
      );

      const escaped = await fs
        .readFile(escapedPath, 'utf8')
        .then(() => true)
        .catch(() => false);
      expect(escaped).toBe(false);
    } finally {
      // If safeTickerSegment ever regresses, this test must still fail without leaking a stray
      // file into the OS temp directory (outside the tempDir this suite's own afterEach cleans).
      await fs.rm(escapedPath, { force: true }).catch(() => {});
    }
  });

  it('still accepts the punctuation real tickers contain', async () => {
    const mock = { ticker: 'BRK.B', epsTtm: 1 } as unknown as StockData;
    await saveCachedStockData('BRK.B', mock, tempDir);
    const back = await getCachedStockData('BRK.B', tempDir);
    expect(back).not.toBeNull();
    expect(back?.ticker).toBe('BRK.B');
  });

  it('saves and retrieves StockData successfully', async () => {
    const mockStock: StockData = {
      ticker: 'AAPL',
      epsTtm: 6.5,
      currentPrice: 180,
      currency: 'USD',
      growth: {
        historical1yPercent: 10,
        historical3yPercent: 12,
        historical5yPercent: 14,
        analystEstimate5yPercent: 15,
        epsTtmGrowthPercent: null,
      },
      historicalPe: { avg1y: 25, avg3y: 26, avg5y: 27 },
      trailingPe: 27.7,
      providerReference: { trailingPe: 27.7, pegRatio: 2.1 },
      staleTtmWarning: false,
      asOf: '2026-08-19T00:00:00.000Z',
    };

    expect(await getCachedStockData('AAPL', tempDir)).toBeNull();

    await saveCachedStockData('AAPL', mockStock, tempDir);

    const retrieved = await getCachedStockData('AAPL', tempDir);
    expect(retrieved).toEqual(mockStock);
  });

  it('saves and retrieves AnalystConsensus successfully', async () => {
    const mockAnalyst: AnalystConsensus = {
      ticker: 'MSFT',
      nextYearEpsGrowthPercent: 18.5,
      priceTarget: {
        mean: 450,
        high: 500,
        low: 400,
        numberOfAnalysts: 35,
      },
      recommendationKey: 'strong_buy',
      beta: null,
      priceToSales: null,
      ruleOf40: null,
      trailingEps: 11.03,
      mostRecentQuarterEndDate: '2026-06-30T00:00:00.000Z',
      asOf: '2026-08-19T00:00:00.000Z',
    };

    expect(await getCachedYahooData('MSFT', tempDir)).toBeNull();

    await saveCachedYahooData('MSFT', mockAnalyst, tempDir);

    const retrieved = await getCachedYahooData('MSFT', tempDir);
    expect(retrieved).toEqual(mockAnalyst);
  });
});
