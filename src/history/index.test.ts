import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import fs from 'node:fs/promises';
import path from 'node:path';
import { saveValuation, getHistory, deleteValuation } from './index';

const TEST_FILE = path.resolve(process.cwd(), 'history-test.json');

describe('history module', () => {
  beforeEach(async () => {
    try {
      await fs.unlink(TEST_FILE);
    } catch {
      // ignore if file doesn't exist
    }
  });

  afterEach(async () => {
    try {
      await fs.unlink(TEST_FILE);
    } catch {
      // ignore
    }
  });

  it('returns empty array when history file does not exist', async () => {
    const result = await getHistory(undefined, TEST_FILE);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data).toEqual([]);
    }
  });

  it('saves a valuation and reads it back', async () => {
    const saveResult = await saveValuation(
      {
        ticker: 'AAPL',
        currentPrice: 220.5,
        currency: 'USD',
        epsTtm: 6.5,
        growthRatePercent: 12,
        exitPeMultiple: 25,
        requiredReturnPercent: 15,
        years: 5,
        lynchFairValue: 156,
        ruleOneFairValue: 180.2,
      },
      TEST_FILE,
    );

    expect(saveResult.ok).toBe(true);
    if (saveResult.ok) {
      expect(saveResult.data.ticker).toBe('AAPL');
      expect(saveResult.data.id).toBeDefined();
      expect(saveResult.data.evaluatedAt).toBeDefined();
    }

    const historyResult = await getHistory(undefined, TEST_FILE);
    expect(historyResult.ok).toBe(true);
    if (historyResult.ok) {
      expect(historyResult.data.length).toBe(1);
      expect(historyResult.data[0].ticker).toBe('AAPL');
      expect(historyResult.data[0].currentPrice).toBe(220.5);
    }
  });

  it('filters history by ticker case-insensitively and sorts newest first', async () => {
    await saveValuation(
      {
        ticker: 'AAPL',
        evaluatedAt: '2026-08-01T10:00:00.000Z',
        currentPrice: 210,
        currency: 'USD',
        epsTtm: 6.0,
        growthRatePercent: 10,
        exitPeMultiple: 20,
        requiredReturnPercent: 15,
        years: 5,
        lynchFairValue: 120,
        ruleOneFairValue: 140,
      },
      TEST_FILE,
    );

    await saveValuation(
      {
        ticker: 'MSFT',
        evaluatedAt: '2026-08-05T10:00:00.000Z',
        currentPrice: 420,
        currency: 'USD',
        epsTtm: 11.5,
        growthRatePercent: 15,
        exitPeMultiple: 30,
        requiredReturnPercent: 15,
        years: 5,
        lynchFairValue: 345,
        ruleOneFairValue: 380,
      },
      TEST_FILE,
    );

    await saveValuation(
      {
        ticker: 'AAPL',
        evaluatedAt: '2026-08-10T10:00:00.000Z',
        currentPrice: 225,
        currency: 'USD',
        epsTtm: 6.5,
        growthRatePercent: 12,
        exitPeMultiple: 25,
        requiredReturnPercent: 15,
        years: 5,
        lynchFairValue: 156,
        ruleOneFairValue: 180,
      },
      TEST_FILE,
    );

    const all = await getHistory(undefined, TEST_FILE);
    expect(all.ok).toBe(true);
    if (all.ok) {
      expect(all.data.length).toBe(3);
      expect(all.data[0].ticker).toBe('AAPL');
      expect(all.data[0].currentPrice).toBe(225); // Newest
    }

    const aaplOnly = await getHistory('aapl', TEST_FILE);
    expect(aaplOnly.ok).toBe(true);
    if (aaplOnly.ok) {
      expect(aaplOnly.data.length).toBe(2);
      expect(aaplOnly.data[0].currentPrice).toBe(225);
      expect(aaplOnly.data[1].currentPrice).toBe(210);
    }
  });

  it('deletes a valuation by id', async () => {
    const saved = await saveValuation(
      {
        id: 'test-id-1',
        ticker: 'GOOGL',
        currentPrice: 170,
        currency: 'USD',
        epsTtm: 7.0,
        growthRatePercent: 14,
        exitPeMultiple: 22,
        requiredReturnPercent: 15,
        years: 5,
        lynchFairValue: 196,
        ruleOneFairValue: 210,
      },
      TEST_FILE,
    );

    expect(saved.ok).toBe(true);

    const deleteRes = await deleteValuation('test-id-1', TEST_FILE);
    expect(deleteRes.ok).toBe(true);

    const afterDelete = await getHistory(undefined, TEST_FILE);
    expect(afterDelete.ok).toBe(true);
    if (afterDelete.ok) {
      expect(afterDelete.data.length).toBe(0);
    }

    const notFoundDelete = await deleteValuation('test-id-1', TEST_FILE);
    expect(notFoundDelete.ok).toBe(false);
    if (!notFoundDelete.ok) {
      expect(notFoundDelete.error.type).toBe('NOT_FOUND');
    }
  });

  it('rejects invalid inputs on save', async () => {
    const res = await saveValuation(
      {
        ticker: '   ',
        currentPrice: 100,
        currency: 'USD',
        epsTtm: 5,
        growthRatePercent: 10,
        exitPeMultiple: 20,
        requiredReturnPercent: 15,
        years: 5,
        lynchFairValue: 100,
        ruleOneFairValue: 100,
      },
      TEST_FILE,
    );

    expect(res.ok).toBe(false);
    if (!res.ok) {
      expect(res.error.type).toBe('INVALID_INPUT');
    }
  });

  it('saves and reads back a 3-scenario (base/bear/bull) record, distinct from the legacy flat shape', async () => {
    // Regression coverage: the web UI's 3-scenario save writes base/bear/bull ScenarioValuation
    // objects instead of the legacy flat fields (src/history/types.ts). Nothing previously
    // confirmed this shape actually round-trips through save/read/filter, only that it type-checks.
    const saveResult = await saveValuation(
      {
        ticker: 'NVDA',
        currentPrice: 300,
        currency: 'USD',
        epsTtm: 12.5,
        years: 10,
        base: {
          growthRatePercent: 20,
          exitPeMultiple: 15,
          requiredReturnPercent: 15,
          mosPercent: 25,
          lynchFairValue: 250,
          ruleOneFairValue: 270,
        },
        bear: {
          growthRatePercent: 15,
          exitPeMultiple: 10,
          requiredReturnPercent: 15,
          mosPercent: 50,
          lynchFairValue: 187.5,
          ruleOneFairValue: 140,
        },
        bull: {
          growthRatePercent: 25,
          exitPeMultiple: 20,
          requiredReturnPercent: 12,
          mosPercent: 10,
          lynchFairValue: 312.5,
          ruleOneFairValue: 400,
        },
        notes: 'scenario round-trip test',
      },
      TEST_FILE,
    );

    expect(saveResult.ok).toBe(true);
    if (!saveResult.ok) return;
    expect(saveResult.data.ticker).toBe('NVDA');
    // The legacy flat fields must NOT be silently populated -- this record is scenario-shaped only.
    expect(saveResult.data.lynchFairValue).toBeUndefined();
    expect(saveResult.data.ruleOneFairValue).toBeUndefined();

    const historyResult = await getHistory('NVDA', TEST_FILE);
    expect(historyResult.ok).toBe(true);
    if (!historyResult.ok) return;
    expect(historyResult.data.length).toBe(1);

    const record = historyResult.data[0];
    expect(record.base).toEqual({
      growthRatePercent: 20,
      exitPeMultiple: 15,
      requiredReturnPercent: 15,
      mosPercent: 25,
      lynchFairValue: 250,
      ruleOneFairValue: 270,
    });
    expect(record.bear?.ruleOneFairValue).toBe(140);
    expect(record.bull?.ruleOneFairValue).toBe(400);
  });
});
