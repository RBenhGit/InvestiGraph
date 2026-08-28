import fs from 'node:fs/promises';
import path from 'node:path';
import { readHistoryFile, writeHistoryFile, PROJECT_ROOT } from './store';
import type {
  SavedValuation,
  SaveValuationInput,
  HistoryResult,
  HistoryError,
} from './types';

export * from './types';

export function formatHistoryError(error: HistoryError): string {
  switch (error.type) {
    case 'IO_ERROR':
      return `File error: ${error.message}`;
    case 'NOT_FOUND':
      return `Valuation record "${error.id}" not found.`;
    case 'INVALID_INPUT':
      return `Invalid input: ${error.reason}`;
  }
}

export async function saveValuation(
  input: SaveValuationInput & { evaluator?: string },
  filePath?: string,
): Promise<HistoryResult<SavedValuation>> {
  if (!input.ticker || typeof input.ticker !== 'string' || input.ticker.trim() === '') {
    return {
      ok: false,
      error: { type: 'INVALID_INPUT', reason: 'Ticker must be a non-empty string.' },
    };
  }

  const ticker = input.ticker.trim().toUpperCase();
  const evaluatedAt = input.evaluatedAt || new Date().toISOString();
  const id = input.id || `${Date.now()}-${ticker}`;
  const { evaluator, ...restInput } = input;

  const record: SavedValuation = {
    ...restInput,
    id,
    ticker,
    evaluatedAt,
    ...(evaluator ? { evaluator } : {}),
  };

  try {
    const existing = await readHistoryFile(filePath, evaluator);
    // Prepend newest at the beginning
    const updated = [record, ...existing.filter((item) => item.id !== id)];
    await writeHistoryFile(updated, filePath, evaluator);
    return { ok: true, data: record };
  } catch (err) {
    return {
      ok: false,
      error: {
        type: 'IO_ERROR',
        message: err instanceof Error ? err.message : String(err),
      },
    };
  }
}

export async function getHistory(
  ticker?: string,
  filePath?: string,
  evaluator?: string,
): Promise<HistoryResult<SavedValuation[]>> {
  try {
    const records = await readHistoryFile(filePath, evaluator);
    
    // Merge legacy history.json records that belong to this evaluator (or have no evaluator)
    if (evaluator && !filePath) {
      try {
        const legacy = await readHistoryFile(); // reads history.json
        const matchingLegacy = legacy.filter(item => !item.evaluator || item.evaluator.toLowerCase() === evaluator.toLowerCase());
        
        // Combine, preferring evaluator file records over legacy ones by ID
        const existingIds = new Set(records.map(r => r.id));
        for (const leg of matchingLegacy) {
          if (!existingIds.has(leg.id)) {
            records.push(leg);
          }
        }
      } catch {
        // No legacy history.json (or it is unreadable) -- nothing to merge in, and that is the
        // normal case for an install that only ever saved under an evaluator.
      }
    }

    // If no evaluator specified, merge all evaluators' files with history.json
    if (!evaluator && !filePath) {
      try {
        const evaluatorsDir = path.resolve(PROJECT_ROOT, 'data', 'evaluators');
        let files: string[] = [];
        try {
          files = await fs.readdir(evaluatorsDir);
        } catch {
          // No data/evaluators/ directory yet -- nobody has saved under an evaluator.
        }
        
        for (const file of files) {
          if (file.endsWith('.json')) {
            const ev = file.replace('.json', '');
            const evRecords = await readHistoryFile(undefined, ev);
            evRecords.forEach(r => r.evaluator = r.evaluator || ev);
            
            const existingIds = new Set(records.map(r => r.id));
            for (const r of evRecords) {
              if (!existingIds.has(r.id)) {
                records.push(r);
              }
            }
          }
        }
      } catch {
        // Merging other evaluators' files is best-effort: a single unreadable file must not
        // fail the caller's own history read.
      }
    }

    let filtered = records;
    if (ticker && ticker.trim() !== '') {
      const target = ticker.trim().toUpperCase();
      filtered = records.filter((item) => item.ticker.toUpperCase() === target);
    }
    // Sort newest first
    filtered.sort((a, b) => new Date(b.evaluatedAt).getTime() - new Date(a.evaluatedAt).getTime());
    return { ok: true, data: filtered };
  } catch (err) {
    return {
      ok: false,
      error: {
        type: 'IO_ERROR',
        message: err instanceof Error ? err.message : String(err),
      },
    };
  }
}

export async function deleteValuation(
  id: string,
  filePath?: string,
  evaluator?: string,
): Promise<HistoryResult<SavedValuation>> {
  if (!id || typeof id !== 'string' || id.trim() === '') {
    return {
      ok: false,
      error: { type: 'INVALID_INPUT', reason: 'ID must be a non-empty string.' },
    };
  }

  try {
    const existing = await readHistoryFile(filePath, evaluator);
    const index = existing.findIndex((item) => item.id === id);
    let deletedItem: SavedValuation | undefined;
    let found = false;

    if (index !== -1) {
      const [deleted] = existing.splice(index, 1);
      deletedItem = deleted;
      found = true;
      await writeHistoryFile(existing, filePath, evaluator);
    }

    // Always check legacy history.json as well, in case there's a stranded copy or 
    // it was never in the evaluator-specific file.
    if (evaluator && !filePath) {
      const legacy = await readHistoryFile();
      const legacyIndex = legacy.findIndex((item) => item.id === id);
      if (legacyIndex !== -1) {
        const [deletedLegacy] = legacy.splice(legacyIndex, 1);
        if (!deletedItem) deletedItem = deletedLegacy;
        found = true;
        await writeHistoryFile(legacy);
      }
    }

    if (!found || !deletedItem) {
      return {
        ok: false,
        error: { type: 'NOT_FOUND', id },
      };
    }
    
    return { ok: true, data: deletedItem };
  } catch (err) {
    return {
      ok: false,
      error: {
        type: 'IO_ERROR',
        message: err instanceof Error ? err.message : String(err),
      },
    };
  }
}


export async function getAllLatestValuations(): Promise<HistoryResult<SavedValuation[]>> {
  try {
    const evaluatorsDir = path.resolve(PROJECT_ROOT, 'data', 'evaluators');
    let files: string[] = [];
    try {
      files = await fs.readdir(evaluatorsDir);
    } catch (err: unknown) {
      // A missing data/evaluators/ directory just means nobody has saved under an evaluator
      // yet. Any other failure is real and must not be swallowed into an empty dashboard.
      if ((err as NodeJS.ErrnoException).code !== 'ENOENT') throw err;
    }

    const allRecords: SavedValuation[] = [];
    const legacy = await readHistoryFile();
    allRecords.push(...legacy);

    for (const file of files) {
      if (file.endsWith('.json')) {
        const evaluator = file.replace('.json', '');
        const records = await readHistoryFile(undefined, evaluator);
        records.forEach(r => r.evaluator = r.evaluator || evaluator);
        allRecords.push(...records);
      }
    }

    // One row per (ticker, evaluator) pair, NOT per ticker. Two people valuing the same
    // ticker are two independent opinions: keying on ticker alone silently dropped whichever
    // was saved earlier, and made the dashboard's own evaluator filter meaningless (only one
    // evaluator's row could ever survive for a given ticker). Legacy records with no evaluator
    // collapse into a single '' bucket per ticker, preserving the pre-evaluator behavior for
    // them. Keyed on a NUL separator so a name containing the separator can't collide across
    // buckets.
    const latestByTickerAndEvaluator = new Map<string, SavedValuation>();
    for (const record of allRecords) {
      const key = `${record.ticker}\u0000${(record.evaluator ?? '').toLowerCase()}`;
      const existing = latestByTickerAndEvaluator.get(key);
      if (
        !existing ||
        new Date(record.evaluatedAt).getTime() > new Date(existing.evaluatedAt).getTime()
      ) {
        latestByTickerAndEvaluator.set(key, record);
      }
    }

    return { ok: true, data: Array.from(latestByTickerAndEvaluator.values()) };
  } catch (err) {
    return {
      ok: false,
      error: {
        type: 'IO_ERROR',
        message: err instanceof Error ? err.message : String(err),
      },
    };
  }
}
