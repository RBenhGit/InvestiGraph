import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import type { StockData } from './twelvedata/types';
import type { AnalystConsensus } from './yahoo/types';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '..', '..');
const DEFAULT_CACHE_DIR = path.resolve(PROJECT_ROOT, 'cache');

export function resolveCacheDir(customDir?: string): string {
  if (customDir) return customDir;
  if (process.env.CACHE_DIR_PATH) return path.resolve(process.env.CACHE_DIR_PATH);
  return DEFAULT_CACHE_DIR;
}

export async function saveCachedStockData(
  ticker: string,
  data: StockData,
  cacheDir?: string,
): Promise<void> {
  try {
    const dir = resolveCacheDir(cacheDir);
    await fs.mkdir(dir, { recursive: true });
    const filePath = path.join(dir, `twelvedata_${ticker.toUpperCase()}.json`);
    await fs.writeFile(filePath, JSON.stringify(data, null, 2), 'utf8');
  } catch {
    // Non-fatal: caching failure should not fail the user's operation
  }
}

export async function getCachedStockData(
  ticker: string,
  cacheDir?: string,
): Promise<StockData | null> {
  try {
    const dir = resolveCacheDir(cacheDir);
    const filePath = path.join(dir, `twelvedata_${ticker.toUpperCase()}.json`);
    const raw = await fs.readFile(filePath, 'utf8');
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === 'object' && parsed.ticker) {
      return parsed as StockData;
    }
    return null;
  } catch {
    return null;
  }
}

export async function saveCachedYahooData(
  ticker: string,
  data: AnalystConsensus,
  cacheDir?: string,
): Promise<void> {
  try {
    const dir = resolveCacheDir(cacheDir);
    await fs.mkdir(dir, { recursive: true });
    const filePath = path.join(dir, `yahoo_${ticker.toUpperCase()}.json`);
    await fs.writeFile(filePath, JSON.stringify(data, null, 2), 'utf8');
  } catch {
    // Non-fatal
  }
}

export async function getCachedYahooData(
  ticker: string,
  cacheDir?: string,
): Promise<AnalystConsensus | null> {
  try {
    const dir = resolveCacheDir(cacheDir);
    const filePath = path.join(dir, `yahoo_${ticker.toUpperCase()}.json`);
    const raw = await fs.readFile(filePath, 'utf8');
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === 'object' && parsed.ticker) {
      return parsed as AnalystConsensus;
    }
    return null;
  } catch {
    return null;
  }
}
