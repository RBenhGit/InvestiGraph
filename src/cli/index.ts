import { Command } from 'commander';
import { fetchStockData } from '../data/twelvedata';
import type { StockDataError } from '../data/twelvedata/types';
import { calculateLynchValue } from '../valuation/lynch';
import { calculateRuleOneValue } from '../valuation/ruleOne';
import { formatOutput } from './formatOutput';

// Assumption defaults for Method B (Rule #1) — live here, not in the valuation layer, so the
// core function stays pure and takes every input explicitly.
const EXIT_PE_MULTIPLE = 15;
const REQUIRED_RETURN_PERCENT = 15;
const YEARS = 10;

/** Renders a `StockDataError` as a one-line, human-readable message. */
function formatStockDataError(error: StockDataError): string {
  switch (error.type) {
    case 'NOT_FOUND':
      return `Ticker "${error.ticker}" not found.`;
    case 'INSUFFICIENT_DATA':
      return `Insufficient data for "${error.ticker}": ${error.reason}`;
    case 'EMPTY_RESPONSE':
      return `Empty response from "${error.endpoint}" for "${error.ticker}".`;
    case 'API_ERROR':
      return `API error from "${error.endpoint}" for "${error.ticker}": ${error.message}`;
    case 'INVALID_CURRENCY_UNIT':
      return `Invalid currency unit for "${error.ticker}": ${error.detail}`;
  }
}

async function run(ticker: string): Promise<void> {
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
  );

  console.log(formatOutput(data, lynchResult, ruleOneResult));
}

const program = new Command();
program
  .name('eps-evaluation')
  .description('EPS-growth x multiple stock valuation (Lynch / Rule #1 style)')
  .argument('<ticker>', 'stock ticker symbol')
  .action((ticker: string) => run(ticker));

program.parseAsync(process.argv);
