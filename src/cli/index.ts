import { Command } from 'commander';
import { fetchStockData } from '../data/twelvedata';
import type { StockDataError } from '../data/twelvedata/types';
import { calculateLynchValue } from '../valuation/lynch';
import { calculateRuleOneValue } from '../valuation/ruleOne';
import { formatOutput } from './formatOutput';
import { saveValuation, getHistory, formatHistoryError, type SavedValuation } from '../history';

// Assumption defaults for Method B (Rule #1) — live here, not in the valuation layer, so the
// core function stays pure and takes every input explicitly.
const EXIT_PE_MULTIPLE = 15;
const REQUIRED_RETURN_PERCENT = 15;
const YEARS = 10;

/** Renders a `StockDataError` as a one-line, human-readable message. */
export function formatStockDataError(error: StockDataError): string {
  switch (error.type) {
    case 'NOT_FOUND':
      return `Ticker "${error.ticker}" not found.`;
    case 'INSUFFICIENT_DATA':
      return `Insufficient data for "${error.ticker}": ${error.reason}`;
    case 'EMPTY_RESPONSE':
      return `Empty response from "${error.endpoint}" for "${error.ticker}".`;
    case 'API_ERROR':
      return `API error from "${error.endpoint}" for "${error.ticker}": ${error.message}`;
    case 'RATE_LIMIT':
      return `Rate limit exceeded from "${error.endpoint}" for "${error.ticker}". Please wait a minute and try again.`;
    case 'INVALID_CURRENCY_UNIT':
      return `Invalid currency unit for "${error.ticker}": ${error.detail}`;
  }
}

export function formatHistoryOutput(records: SavedValuation[]): string {
  if (records.length === 0) {
    return 'No saved valuations found.';
  }
  const lines: string[] = [];
  lines.push(
    '----------------------------------------------------------------------------------------------------------------------------------',
  );
  lines.push(
    'Date                 Ticker   Price        Lynch FV   Rule #1 FV  Growth %   Assumptions            Notes',
  );
  lines.push(
    '----------------------------------------------------------------------------------------------------------------------------------',
  );
  for (const r of records) {
    // Web-saved records only populate base/bear/bull (added for the 3-scenario feature); the
    // CLI's own --save still writes the legacy flat fields. Read whichever shape is present so
    // this table renders correctly for records from either adapter.
    const scenario = r.base ?? r;
    const d = r.evaluatedAt ? r.evaluatedAt.replace('T', ' ').slice(0, 16) : 'n/a';
    const ticker = r.ticker.padEnd(8);
    // readHistoryFile only guarantees a string `ticker` on a hand-edited history.json -- a
    // record missing currentPrice (or any other field) still passes that filter, so this must
    // not assume currentPrice is a number the way the rest of this function already treats every
    // other optional field as possibly absent.
    const price = (
      typeof r.currentPrice === 'number'
        ? `${r.currentPrice.toFixed(2)} ${r.currency || 'USD'}`
        : 'n/a'
    ).padEnd(12);
    const lynchFv = scenario.lynchFairValue;
    const ruleOneFv = scenario.ruleOneFairValue;
    const growthPct = scenario.growthRatePercent;
    const lynch = (lynchFv !== null && lynchFv !== undefined ? lynchFv.toFixed(2) : 'n/a').padEnd(
      10,
    );
    const ruleOne = (
      ruleOneFv !== null && ruleOneFv !== undefined ? ruleOneFv.toFixed(2) : 'n/a'
    ).padEnd(11);
    const growth =
      `${growthPct !== null && growthPct !== undefined ? growthPct.toFixed(2) : 'n/a'}%`.padEnd(10);
    const mosStr = scenario.mosPercent ? ` MoS:${scenario.mosPercent}%` : '';
    const assump =
      `PE:${scenario.exitPeMultiple ?? 'n/a'} Req:${scenario.requiredReturnPercent ?? 'n/a'}% ${r.years}y${mosStr}`.padEnd(
        22,
      );
    const notes = r.notes ? r.notes : '';
    lines.push(
      `${d.padEnd(20)} ${ticker} ${price} ${lynch} ${ruleOne} ${growth} ${assump} ${notes}`,
    );
  }
  lines.push(
    '----------------------------------------------------------------------------------------------------------------------------------',
  );
  return lines.join('\n');
}

async function showHistory(ticker?: string): Promise<void> {
  const result = await getHistory(ticker);
  if (!result.ok) {
    console.error(`Error loading history: ${formatHistoryError(result.error)}`);
    process.exitCode = 1;
    return;
  }
  console.log(formatHistoryOutput(result.data));
}

async function run(
  ticker: string,
  shouldSave = false,
  mosPercent = 0,
  notes?: string,
): Promise<void> {
  const result = await fetchStockData(ticker);

  if (!result.ok) {
    console.error(`Error: ${formatStockDataError(result.error)}`);
    process.exitCode = 1;
    return;
  }

  const { data } = result;
  // Note: This growth fallback chain is duplicated in web/public/app.js.
  // If you change the fallback logic here, make sure to update the web UI as well.
  const growthSeed =
    data.growth.analystEstimate5yPercent ??
    data.growth.historical3yPercent ??
    data.growth.historical1yPercent ??
    null;

  const lynchResult = calculateLynchValue(data.epsTtm, growthSeed);
  const ruleOneResult = calculateRuleOneValue(
    data.epsTtm,
    growthSeed,
    EXIT_PE_MULTIPLE,
    REQUIRED_RETURN_PERCENT,
    YEARS,
    mosPercent,
  );

  console.log(formatOutput(data, lynchResult, ruleOneResult));

  if (shouldSave && growthSeed !== null) {
    const saveResult = await saveValuation({
      ticker: data.ticker,
      currentPrice: data.currentPrice,
      currency: data.currency,
      epsTtm: data.epsTtm,
      growthRatePercent: growthSeed,
      exitPeMultiple: EXIT_PE_MULTIPLE,
      requiredReturnPercent: REQUIRED_RETURN_PERCENT,
      years: YEARS,
      mosPercent,
      lynchFairValue: lynchResult.ok ? lynchResult.fairValue : null,
      ruleOneFairValue: ruleOneResult.ok ? ruleOneResult.fairValue : null,
      notes,
    });
    if (saveResult.ok) {
      console.log('\n✓ Valuation saved to history.');
    } else {
      console.error(
        `\nFailed to save valuation to history: ${formatHistoryError(saveResult.error)}`,
      );
    }
  }
}

const program = new Command();
program
  .name('eps-evaluation')
  .description('EPS-growth x multiple stock valuation (Lynch / Rule #1 style)')
  .argument('[ticker]', 'stock ticker symbol')
  .option('-s, --save', 'save the valuation result to history')
  .option('-m, --mos <percent>', 'Margin of Safety percent for Rule #1 (e.g. 25 for 25%)', '0')
  .option('-n, --notes <text>', 'notes or investment thesis to attach to saved valuation')
  .option('-H, --history [ticker]', 'view historical valuations (optional: filter by ticker)')
  .action(
    async (
      tickerArg?: string,
      options?: {
        save?: boolean;
        history?: boolean | string;
        mos?: string;
        notes?: string;
      },
    ) => {
      if (options?.history !== undefined) {
        const filter =
          typeof options.history === 'string' ? options.history : tickerArg || undefined;
        await showHistory(filter);
        return;
      }
      if (!tickerArg) {
        console.error('Error: Please provide a ticker symbol or use --history.');
        process.exitCode = 1;
        return;
      }
      const mosPercent = options?.mos ? Number(options.mos) : 0;
      await run(tickerArg, Boolean(options?.save), mosPercent, options?.notes);
    },
  );

program.parseAsync(process.argv);
