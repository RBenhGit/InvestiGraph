import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import type { SavedValuation } from './types';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
export const PROJECT_ROOT = path.resolve(__dirname, '..', '..');
const DEFAULT_HISTORY_FILE = path.resolve(PROJECT_ROOT, 'history.json');

export function resolveHistoryFilePath(customPath?: string, evaluator?: string): string {
  if (customPath) return customPath;
  if (process.env.HISTORY_FILE_PATH) return path.resolve(process.env.HISTORY_FILE_PATH);
  
  if (evaluator && typeof evaluator === 'string' && evaluator.trim() !== '') {
    const safeName = evaluator.trim().toLowerCase().replace(/[^a-z0-9_-]/g, '');
    return path.resolve(PROJECT_ROOT, 'data', 'evaluators', `${safeName}.json`);
  }
  return DEFAULT_HISTORY_FILE;
}

export async function readHistoryFile(filePath?: string, evaluator?: string): Promise<SavedValuation[]> {
  const target = resolveHistoryFilePath(filePath, evaluator);
  try {
    const raw = await fs.readFile(target, 'utf8');
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    // history.json is a plain file a user can hand-edit, and Array.isArray says nothing about
    // the ELEMENTS: a stray `null` or a bare string sails through and then throws on the first
    // property access downstream (`getHistory`'s ticker filter, and the web UI's history table,
    // which loses the whole render). Drop entries that cannot be records; a corrupt line should
    // cost its own row, not the entire history.
    const valid = parsed.filter(
      (item): item is SavedValuation =>
        typeof item === 'object' &&
        item !== null &&
        typeof (item as SavedValuation).ticker === 'string',
    );
    // A dropped entry here is gone for good the next time anything calls writeHistoryFile (the
    // next unrelated save/delete persists the filtered array back to disk) -- silently turning
    // "this row won't render" into permanent data loss. Not silent any more.
    if (valid.length !== parsed.length) {
      console.warn(
        `history.json: dropped ${parsed.length - valid.length} malformed entr${parsed.length - valid.length === 1 ? 'y' : 'ies'} (missing/non-string ticker)`,
      );
    }
    return valid;
  } catch (err: unknown) {
    if (
      typeof err === 'object' &&
      err !== null &&
      'code' in err &&
      (err as { code: string }).code === 'ENOENT'
    ) {
      return [];
    }
    throw err;
  }
}

export async function writeHistoryFile(
  records: SavedValuation[],
  filePath?: string,
  evaluator?: string,
): Promise<void> {
  const target = resolveHistoryFilePath(filePath, evaluator);
  await fs.mkdir(path.dirname(target), { recursive: true });
  const data = JSON.stringify(records, null, 2);
  await fs.writeFile(target, data, 'utf8');
}
