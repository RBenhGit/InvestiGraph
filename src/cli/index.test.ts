import { describe, it, expect, vi } from 'vitest';

vi.mock('commander', () => {
  return {
    Command: class {
      name() {
        return this;
      }
      description() {
        return this;
      }
      argument() {
        return this;
      }
      option() {
        return this;
      }
      action() {
        return this;
      }
      parseAsync() {
        return Promise.resolve();
      }
    },
  };
});

import { formatStockDataError, formatHistoryOutput } from './index';
import type { StockDataError } from '../data/twelvedata/types';
import type { SavedValuation } from '../history';

describe('formatStockDataError', () => {
  it('formats NOT_FOUND error', () => {
    const error: StockDataError = { type: 'NOT_FOUND', ticker: 'XYZ' };
    expect(formatStockDataError(error)).toBe('Ticker "XYZ" not found.');
  });

  it('formats INSUFFICIENT_DATA error', () => {
    const error: StockDataError = {
      type: 'INSUFFICIENT_DATA',
      ticker: 'XYZ',
      reason: 'Missing EPS',
    };
    expect(formatStockDataError(error)).toBe('Insufficient data for "XYZ": Missing EPS');
  });

  it('formats EMPTY_RESPONSE error', () => {
    const error: StockDataError = {
      type: 'EMPTY_RESPONSE',
      ticker: 'XYZ',
      endpoint: 'quote',
    };
    expect(formatStockDataError(error)).toBe('Empty response from "quote" for "XYZ".');
  });

  it('formats API_ERROR error', () => {
    const error: StockDataError = {
      type: 'API_ERROR',
      ticker: 'XYZ',
      endpoint: 'statistics',
      message: 'Server down',
    };
    expect(formatStockDataError(error)).toBe('API error from "statistics" for "XYZ": Server down');
  });

  it('formats INVALID_CURRENCY_UNIT error', () => {
    const error: StockDataError = {
      type: 'INVALID_CURRENCY_UNIT',
      ticker: 'XYZ',
      detail: 'Mismatched currencies',
    };
    expect(formatStockDataError(error)).toBe(
      'Invalid currency unit for "XYZ": Mismatched currencies',
    );
  });
});

describe('formatHistoryOutput', () => {
  it('returns empty message when records array is empty', () => {
    expect(formatHistoryOutput([])).toBe('No saved valuations found.');
  });

  it('formats history records into a clean table', () => {
    const records: SavedValuation[] = [
      {
        id: '1',
        ticker: 'AAPL',
        evaluatedAt: '2026-08-19T18:45:00.000Z',
        currentPrice: 220.5,
        currency: 'USD',
        epsTtm: 6.5,
        growthRatePercent: 12.0,
        exitPeMultiple: 15,
        requiredReturnPercent: 15,
        years: 10,
        lynchFairValue: 156.0,
        ruleOneFairValue: 180.2,
      },
    ];
    const output = formatHistoryOutput(records);
    expect(output).toContain('AAPL');
    expect(output).toContain('220.50 USD');
    expect(output).toContain('156.00');
    expect(output).toContain('180.20');
    expect(output).toContain('12.00%');
  });

  it('renders a record missing currentPrice as n/a instead of throwing', () => {
    // Regression: readHistoryFile's corruption filter only guarantees `ticker` is a string --
    // a hand-edited history.json entry missing currentPrice (or any other field) still passes
    // it. formatHistoryOutput previously called r.currentPrice.toFixed(2) unguarded, crashing
    // the entire `-H` listing on this one incomplete record.
    const records = [
      { id: 'good-1', ticker: 'AAPL', evaluatedAt: '2026-08-01T00:00:00.000Z', years: 10 },
    ] as unknown as SavedValuation[];

    expect(() => formatHistoryOutput(records)).not.toThrow();
    const output = formatHistoryOutput(records);
    expect(output).toContain('AAPL');
    expect(output).toContain('n/a');
  });

  it('formats history records with MoS and Notes included', () => {
    const records: SavedValuation[] = [
      {
        id: '2',
        ticker: 'MSFT',
        evaluatedAt: '2026-08-19T18:45:00.000Z',
        currentPrice: 400.0,
        currency: 'USD',
        epsTtm: 11.5,
        growthRatePercent: 14.0,
        exitPeMultiple: 20,
        requiredReturnPercent: 15,
        years: 10,
        mosPercent: 25,
        lynchFairValue: 300.0,
        ruleOneFairValue: 275.0,
        notes: 'Conservative growth assumption',
      },
    ];
    const output = formatHistoryOutput(records);
    expect(output).toContain('MSFT');
    expect(output).toContain('MoS:25%');
    expect(output).toContain('Conservative growth assumption');
  });
});
