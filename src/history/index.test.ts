import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { saveValuation, getHistory, deleteValuation, getAllLatestValuations } from './index';
import type { SaveValuationInput } from './types';
import { resolveHistoryFilePath, PROJECT_ROOT } from './store';

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

describe('readHistoryFile resilience to a hand-edited file', () => {
  it('skips malformed entries instead of throwing on the whole history', async () => {
    const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'hist-corrupt-'));
    const file = path.join(dir, 'history.json');
    try {
      await fs.writeFile(
        file,
        JSON.stringify([
          null,
          'not-a-record',
          42,
          { id: 'good-1', ticker: 'AAPL', evaluatedAt: '2026-08-01T00:00:00.000Z', years: 10 },
        ]),
        'utf8',
      );

      // Without the guard this throws "Cannot read properties of null (reading 'ticker')".
      const all = await getHistory(undefined, file);
      expect(all.ok).toBe(true);
      if (all.ok) {
        expect(all.data).toHaveLength(1);
        expect(all.data[0].id).toBe('good-1');
      }

      const filtered = await getHistory('AAPL', file);
      expect(filtered.ok).toBe(true);
      if (filtered.ok) expect(filtered.data).toHaveLength(1);
    } finally {
      await fs.rm(dir, { recursive: true, force: true }).catch(() => {});
    }
  });
});

// ---------------------------------------------------------------------------
// Evaluator-scoped storage (data/evaluators/<name>.json)
//
// These exercise the real on-disk paths rather than an injected filePath, because the
// evaluator branch of resolveHistoryFilePath is only reachable when NO explicit path is
// passed -- an explicit filePath short-circuits it (and also disables the legacy-merge
// branches in getHistory), so a path-injecting test can never reach this code at all.
// Everything here is namespaced under vitest-only evaluator names and tickers so it can
// never collide with (or assert against) a real user's saved valuations.
// ---------------------------------------------------------------------------
describe('evaluator-scoped history storage', () => {
  const EVALUATOR_A = 'VitestEvalA';
  const EVALUATOR_B = 'VitestEvalB';
  const EVAL_A_FILE = path.resolve(PROJECT_ROOT, 'data', 'evaluators', 'vitestevala.json');
  const EVAL_B_FILE = path.resolve(PROJECT_ROOT, 'data', 'evaluators', 'vitestevalb.json');
  const LEGACY_FILE = path.resolve(PROJECT_ROOT, 'history.json');
  const TICKER = 'ZZVITEST';

  // resolveHistoryFilePath checks HISTORY_FILE_PATH *before* the evaluator, so a stray env var
  // would silently route every read/write below back to a single shared file.
  const savedEnv = process.env.HISTORY_FILE_PATH;
  // history.json is a real user file on a real install. Never replace it -- capture its exact
  // bytes, append to it, and put the original back afterwards (or remove it if we created it).
  let legacyBackup: string | null = null;

  beforeEach(async () => {
    delete process.env.HISTORY_FILE_PATH;
    try {
      legacyBackup = await fs.readFile(LEGACY_FILE, 'utf8');
    } catch {
      legacyBackup = null;
    }
    await fs.rm(EVAL_A_FILE, { force: true });
    await fs.rm(EVAL_B_FILE, { force: true });
  });

  afterEach(async () => {
    if (savedEnv === undefined) {
      delete process.env.HISTORY_FILE_PATH;
    } else {
      process.env.HISTORY_FILE_PATH = savedEnv;
    }
    await fs.rm(EVAL_A_FILE, { force: true });
    await fs.rm(EVAL_B_FILE, { force: true });
    if (legacyBackup !== null) {
      await fs.writeFile(LEGACY_FILE, legacyBackup, 'utf8');
    } else {
      await fs.rm(LEGACY_FILE, { force: true });
    }
  });

  function record(overrides: Partial<SaveValuationInput> = {}): SaveValuationInput {
    return {
      ticker: TICKER,
      currentPrice: 100,
      currency: 'USD',
      epsTtm: 5,
      years: 10,
      base: {
        growthRatePercent: 10,
        exitPeMultiple: 15,
        requiredReturnPercent: 15,
        mosPercent: 0,
        lynchFairValue: 75,
        ruleOneFairValue: 60,
      },
      ...overrides,
    };
  }

  it('routes a save with an evaluator to data/evaluators/<sanitized-name>.json, not history.json', async () => {
    const saved = await saveValuation({ ...record(), evaluator: EVALUATOR_A });
    expect(saved.ok).toBe(true);

    // The name is lower-cased and stripped to [a-z0-9_-] before being used as a filename.
    const onDisk = JSON.parse(await fs.readFile(EVAL_A_FILE, 'utf8'));
    expect(onDisk).toHaveLength(1);
    expect(onDisk[0].ticker).toBe(TICKER);
    expect(onDisk[0].evaluator).toBe(EVALUATOR_A);
  });

  it('strips characters that are illegal in a filename from the evaluator name', async () => {
    const saved = await saveValuation({ ...record(), evaluator: 'Vitest Eval A!' });
    expect(saved.ok).toBe(true);
    // 'Vitest Eval A!' -> 'vitestevala' (spaces and punctuation removed, lower-cased)
    const onDisk = JSON.parse(await fs.readFile(EVAL_A_FILE, 'utf8'));
    expect(onDisk[0].evaluator).toBe('Vitest Eval A!');
  });

  it('reads back only that evaluator’s own records, not another evaluator’s', async () => {
    await saveValuation({ ...record({ id: 'a-1' }), evaluator: EVALUATOR_A });
    await saveValuation({ ...record({ id: 'b-1' }), evaluator: EVALUATOR_B });

    const a = await getHistory(TICKER, undefined, EVALUATOR_A);
    expect(a.ok).toBe(true);
    if (a.ok) {
      expect(a.data.map((r) => r.id)).toEqual(['a-1']);
    }
  });

  it('merges legacy history.json records with no evaluator into an evaluator’s history', async () => {
    // A record saved before the evaluator feature existed: flat legacy shape, no evaluator.
    const legacy = legacyBackup === null ? [] : JSON.parse(legacyBackup);
    legacy.push({
      id: 'legacy-1',
      ticker: TICKER,
      evaluatedAt: '2026-01-01T00:00:00.000Z',
      currentPrice: 90,
      currency: 'USD',
      epsTtm: 5,
      years: 10,
      lynchFairValue: 70,
      ruleOneFairValue: 55,
    });
    await fs.writeFile(LEGACY_FILE, JSON.stringify(legacy, null, 2), 'utf8');

    await saveValuation({ ...record({ id: 'a-1' }), evaluator: EVALUATOR_A });

    const result = await getHistory(TICKER, undefined, EVALUATOR_A);
    expect(result.ok).toBe(true);
    if (result.ok) {
      // Both the evaluator's own record and the un-owned legacy one are visible to this
      // evaluator -- that is the whole point of the merge (old records aren't orphaned).
      expect(result.data.map((r) => r.id).sort()).toEqual(['a-1', 'legacy-1']);
    }
  });

  it('does NOT merge a legacy record that belongs to a different evaluator', async () => {
    const legacy = legacyBackup === null ? [] : JSON.parse(legacyBackup);
    legacy.push({
      id: 'legacy-owned',
      ticker: TICKER,
      evaluatedAt: '2026-01-01T00:00:00.000Z',
      currentPrice: 90,
      currency: 'USD',
      epsTtm: 5,
      years: 10,
      evaluator: EVALUATOR_B,
    });
    await fs.writeFile(LEGACY_FILE, JSON.stringify(legacy, null, 2), 'utf8');

    await saveValuation({ ...record({ id: 'a-1' }), evaluator: EVALUATOR_A });

    const result = await getHistory(TICKER, undefined, EVALUATOR_A);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.map((r) => r.id)).toEqual(['a-1']);
    }
  });

  describe('getAllLatestValuations', () => {
    it('keeps one row per (ticker, evaluator) pair — two evaluators on the same ticker both survive', async () => {
      await saveValuation({
        ...record({ id: 'a-1', evaluatedAt: '2026-02-01T00:00:00.000Z' }),
        evaluator: EVALUATOR_A,
      });
      await saveValuation({
        ...record({ id: 'b-1', evaluatedAt: '2026-03-01T00:00:00.000Z' }),
        evaluator: EVALUATOR_B,
      });

      const result = await getAllLatestValuations();
      expect(result.ok).toBe(true);
      if (result.ok) {
        const mine = result.data.filter((r) => r.ticker === TICKER);
        // Keyed on ticker alone (the previous behavior) this returned only 'b-1', silently
        // hiding evaluator A's opinion and making the dashboard's evaluator filter pointless.
        expect(mine.map((r) => r.id).sort()).toEqual(['a-1', 'b-1']);
      }
    });

    it('still keeps only the most recent record within a single (ticker, evaluator) pair', async () => {
      await saveValuation({
        ...record({ id: 'a-old', evaluatedAt: '2026-01-01T00:00:00.000Z' }),
        evaluator: EVALUATOR_A,
      });
      await saveValuation({
        ...record({ id: 'a-new', evaluatedAt: '2026-06-01T00:00:00.000Z' }),
        evaluator: EVALUATOR_A,
      });

      const result = await getAllLatestValuations();
      expect(result.ok).toBe(true);
      if (result.ok) {
        const mine = result.data.filter((r) => r.ticker === TICKER);
        expect(mine.map((r) => r.id)).toEqual(['a-new']);
      }
    });
  });
});

// ---------------------------------------------------------------------------
// resolveHistoryFilePath's own branches. index.test.ts above always passes an explicit
// filePath, so the env-var and default-path branches were never executed by any test.
// ---------------------------------------------------------------------------
describe('resolveHistoryFilePath', () => {
  const savedEnv = process.env.HISTORY_FILE_PATH;

  afterEach(() => {
    if (savedEnv === undefined) {
      delete process.env.HISTORY_FILE_PATH;
    } else {
      process.env.HISTORY_FILE_PATH = savedEnv;
    }
  });

  it('prefers an explicit path over everything else', () => {
    process.env.HISTORY_FILE_PATH = '/tmp/from-env.json';
    expect(resolveHistoryFilePath('/tmp/explicit.json', 'Someone')).toBe('/tmp/explicit.json');
  });

  it('uses HISTORY_FILE_PATH when set, resolved to an absolute path', () => {
    delete process.env.HISTORY_FILE_PATH;
    process.env.HISTORY_FILE_PATH = './relative-history.json';
    expect(resolveHistoryFilePath()).toBe(path.resolve('./relative-history.json'));
  });

  it('HISTORY_FILE_PATH takes precedence over the evaluator, collapsing per-evaluator storage into one file', () => {
    process.env.HISTORY_FILE_PATH = '/tmp/from-env.json';
    // Documented consequence, not an accident: setting this env var disables per-evaluator
    // history entirely, because it is checked before the evaluator branch.
    expect(resolveHistoryFilePath(undefined, 'Someone')).toBe('/tmp/from-env.json');
  });

  it('falls back to <project root>/history.json when nothing is set', () => {
    delete process.env.HISTORY_FILE_PATH;
    expect(resolveHistoryFilePath()).toBe(path.resolve(PROJECT_ROOT, 'history.json'));
  });

  it('routes to data/evaluators/<sanitized>.json for an evaluator, ignoring case and punctuation', () => {
    delete process.env.HISTORY_FILE_PATH;
    expect(resolveHistoryFilePath(undefined, '  Aviv Cohen!  ')).toBe(
      path.resolve(PROJECT_ROOT, 'data', 'evaluators', 'avivcohen.json'),
    );
  });

  it('treats a blank/whitespace-only evaluator as no evaluator at all', () => {
    delete process.env.HISTORY_FILE_PATH;
    expect(resolveHistoryFilePath(undefined, '   ')).toBe(
      path.resolve(PROJECT_ROOT, 'history.json'),
    );
  });
});
