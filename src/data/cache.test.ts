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
      },
      historicalPe: { avg1y: 25, avg3y: 26, avg5y: 27 },
      trailingPe: 27.7,
      providerReference: { trailingPe: 27.7, pegRatio: 2.1 },
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
      asOf: '2026-08-19T00:00:00.000Z',
    };

    expect(await getCachedYahooData('MSFT', tempDir)).toBeNull();

    await saveCachedYahooData('MSFT', mockAnalyst, tempDir);

    const retrieved = await getCachedYahooData('MSFT', tempDir);
    expect(retrieved).toEqual(mockAnalyst);
  });
});
