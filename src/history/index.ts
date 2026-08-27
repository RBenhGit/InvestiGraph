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
    let records = await readHistoryFile(filePath, evaluator);
    
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
      } catch (err: any) {
        // ignore if history.json doesn't exist
      }
    }

    // If no evaluator specified, merge all evaluators' files with history.json
    if (!evaluator && !filePath) {
      try {
        const evaluatorsDir = path.resolve(PROJECT_ROOT, 'data', 'evaluators');
        let files: string[] = [];
        try { files = await fs.readdir(evaluatorsDir); } catch (e) {}
        
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
      } catch (err: any) {
        // ignore
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
    if (index === -1) {
      return {
        ok: false,
        error: { type: 'NOT_FOUND', id },
      };
    }
    const [deleted] = existing.splice(index, 1);
    await writeHistoryFile(existing, filePath, evaluator);
    return { ok: true, data: deleted };
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
    } catch (err: any) {
      if (err.code !== 'ENOENT') throw err;
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

    const latestByTicker = new Map<string, SavedValuation>();
    for (const record of allRecords) {
      const existing = latestByTicker.get(record.ticker);
      if (!existing || new Date(record.evaluatedAt).getTime() > new Date(existing.evaluatedAt).getTime()) {
        latestByTicker.set(record.ticker, record);
      }
    }

    return { ok: true, data: Array.from(latestByTicker.values()) };
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
