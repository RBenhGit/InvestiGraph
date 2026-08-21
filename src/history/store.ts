import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import type { SavedValuation } from './types';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '..', '..');
const DEFAULT_HISTORY_FILE = path.resolve(PROJECT_ROOT, 'history.json');

export function resolveHistoryFilePath(customPath?: string): string {
  if (customPath) return customPath;
  if (process.env.HISTORY_FILE_PATH) return path.resolve(process.env.HISTORY_FILE_PATH);
  return DEFAULT_HISTORY_FILE;
}

export async function readHistoryFile(filePath?: string): Promise<SavedValuation[]> {
  const target = resolveHistoryFilePath(filePath);
  try {
    const raw = await fs.readFile(target, 'utf8');
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed;
  } catch (err: unknown) {
    if (typeof err === 'object' && err !== null && 'code' in err && (err as { code: string }).code === 'ENOENT') {
      return [];
    }
    throw err;
  }
}

export async function writeHistoryFile(
  records: SavedValuation[],
  filePath?: string,
): Promise<void> {
  const target = resolveHistoryFilePath(filePath);
  const data = JSON.stringify(records, null, 2);
  await fs.writeFile(target, data, 'utf8');
}
