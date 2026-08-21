import { readHistoryFile, writeHistoryFile } from './store';
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
  input: SaveValuationInput,
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

  const record: SavedValuation = {
    ...input,
    id,
    ticker,
    evaluatedAt,
  };

  try {
    const existing = await readHistoryFile(filePath);
    // Prepend newest at the beginning
    const updated = [record, ...existing.filter((item) => item.id !== id)];
    await writeHistoryFile(updated, filePath);
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
): Promise<HistoryResult<SavedValuation[]>> {
  try {
    const records = await readHistoryFile(filePath);
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
): Promise<HistoryResult<SavedValuation>> {
  if (!id || typeof id !== 'string' || id.trim() === '') {
    return {
      ok: false,
      error: { type: 'INVALID_INPUT', reason: 'ID must be a non-empty string.' },
    };
  }

  try {
    const existing = await readHistoryFile(filePath);
    const index = existing.findIndex((item) => item.id === id);
    if (index === -1) {
      return {
        ok: false,
        error: { type: 'NOT_FOUND', id },
      };
    }
    const [deleted] = existing.splice(index, 1);
    await writeHistoryFile(existing, filePath);
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
