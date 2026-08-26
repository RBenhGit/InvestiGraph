import type { StockData } from '../data/twelvedata/types';
import type { ResolvedEps } from '../data/resolveEps';
import type { RuleOneInputsUsed } from '../valuation/ruleOne';
import type { ValuationInputsUsed, ValuationResult } from '../valuation/shared/types';

/** Formats a number to 2 decimal places, or `'n/a'` when the value is `null`. */
function fmt(value: number | null): string {
  return value === null ? 'n/a' : value.toFixed(2);
}

/** Picks the growth-rate seed that would have fed both valuation calls, purely for display —
 * mirrors the same fallback chain `cli/index.ts` uses to build the value it actually passes in. */
function selectGrowthSource(data: StockData): { value: number | null; label: string } {
  if (data.growth.analystEstimate5yPercent !== null) {
    return { value: data.growth.analystEstimate5yPercent, label: 'analyst 5y estimate' };
  }
  if (data.growth.historical3yPercent !== null) {
    return { value: data.growth.historical3yPercent, label: 'historical 3y' };
  }
  if (data.growth.historical1yPercent !== null) {
    return { value: data.growth.historical1yPercent, label: 'historical 1y' };
  }
  return { value: null, label: 'none available' };
}

/** Picks the `inputs` from whichever result succeeded, so the raw-vs-clamped growth rate can be
 * shown even if one of the two methods failed for a reason unrelated to the growth rate. */
function pickInputsUsed(
  lynchResult: ValuationResult<ValuationInputsUsed>,
  ruleOneResult: ValuationResult<RuleOneInputsUsed>,
): ValuationInputsUsed | null {
  if (lynchResult.ok) return lynchResult.inputs;
  if (ruleOneResult.ok) return ruleOneResult.inputs;
  return null;
}

function formatMethodLine(label: string, result: ValuationResult<ValuationInputsUsed>): string {
  if (result.ok) {
    return `${label}: ${fmt(result.fairValue)}`;
  }
  return `${label}: FAILED (${result.error})`;
}

function formatRuleOneLine(result: ValuationResult<RuleOneInputsUsed>): string {
  if (!result.ok) {
    return `Method B (Rule #1) fair value: FAILED (${result.error})`;
  }
  if (result.inputs.mosPercent && result.inputs.mosPercent > 0) {
    const sticker = result.intermediate?.stickerPrice ?? result.fairValue;
    return `Method B (Rule #1, MoS ${result.inputs.mosPercent}%) fair value: ${fmt(result.fairValue)} (Sticker: ${fmt(sticker)})`;
  }
  return `Method B (Rule #1) fair value: ${fmt(result.fairValue)}`;
}

export function formatOutput(
  data: StockData,
  lynchResult: ValuationResult<ValuationInputsUsed>,
  ruleOneResult: ValuationResult<RuleOneInputsUsed>,
  resolvedEps?: ResolvedEps,
): string {
  const growthSource = selectGrowthSource(data);
  const inputsUsed = pickInputsUsed(lynchResult, ruleOneResult);

  const lines: string[] = [];
  lines.push(`Ticker: ${data.ticker}`);
  lines.push(`Current price: ${fmt(data.currentPrice)} ${data.currency}`);

  if (!resolvedEps || resolvedEps.source === 'twelvedata') {
    lines.push(`EPS (TTM): ${fmt(data.epsTtm)}`);
    if (data.staleTtmWarning) {
      lines.push(
        '  ⚠ WARNING: EPS (TTM) may be stale — it diverges >5% from the provider\'s own trailing P/E-implied EPS. This can happen when a ticker\'s income-statement data has not yet rolled in a recent earnings release.',
      );
    }
  } else if (resolvedEps.source === 'yahoo-fallback') {
    lines.push(`EPS (TTM): ${fmt(resolvedEps.epsTtm)} [source: Yahoo Finance, not Twelve Data]`);
    lines.push(
      `  ⓘ Twelve Data's EPS ($${fmt(data.epsTtm)}) looked stale (>5% off its own trailing P/E) — used Yahoo Finance instead.`,
    );
    lines.push(`  ${resolvedEps.detail}`);
  } else {
    // twelvedata-stale-no-fallback: flagged as possibly stale AND Yahoo was unavailable.
    lines.push(`EPS (TTM): ${fmt(data.epsTtm)} [source: Twelve Data — Yahoo fallback unavailable]`);
    lines.push(
      '  ⚠ WARNING: EPS (TTM) may be stale — it diverges >5% from the provider\'s own trailing P/E-implied EPS, and Yahoo Finance (the fallback source) could not be reached to cross-check.',
    );
  }
  lines.push('');
  lines.push(`Growth rate used: ${fmt(growthSource.value)}% (source: ${growthSource.label})`);
  if (inputsUsed) {
    const { growthRatePercentRaw, growthRatePercentClamped } = inputsUsed;
    if (growthRatePercentRaw !== growthRatePercentClamped) {
      lines.push(
        `  raw: ${fmt(growthRatePercentRaw)}%  clamped: ${fmt(growthRatePercentClamped)}% (clamp applied)`,
      );
    } else {
      lines.push(`  raw: ${fmt(growthRatePercentRaw)}%  clamped: ${fmt(growthRatePercentClamped)}%`);
    }
  }
  lines.push('');
  lines.push(formatMethodLine('Method A (Lynch) fair value', lynchResult));
  lines.push(formatRuleOneLine(ruleOneResult));
  lines.push('');
  lines.push('Historical P/E averages:');
  lines.push(`  1y: ${fmt(data.historicalPe.avg1y)}`);
  lines.push(`  3y: ${fmt(data.historicalPe.avg3y)}`);
  lines.push(`  5y: ${fmt(data.historicalPe.avg5y)}`);
  lines.push('');
  // EPS TTM growth (rolling 12-month vs. 12-month-ago window) — distinct from the calendar-year
  // CAGR figures above and never used by either valuation method; reference only. Needs 8
  // consecutive quarters, which this plan tier's income_statement cap (6) cannot supply today —
  // see calculateTtmEpsGrowthPercent's own comment for why a shorter-window approximation is
  // deliberately never substituted, so this is "n/a" rather than a misleading number.
  lines.push(`EPS TTM growth (YoY, reference only): ${fmt(data.growth.epsTtmGrowthPercent)}%`);
  lines.push('');
  lines.push('Provider reference (not used in valuation):');
  lines.push(`  Trailing P/E: ${fmt(data.providerReference.trailingPe)}`);
  lines.push(`  PEG ratio: ${fmt(data.providerReference.pegRatio)}`);

  return lines.join('\n');
}
