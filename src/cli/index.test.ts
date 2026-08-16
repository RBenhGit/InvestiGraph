import { describe, it, expect, vi } from 'vitest';

vi.mock('commander', () => {
  return {
    Command: class {
      name() { return this; }
      description() { return this; }
      argument() { return this; }
      action() { return this; }
      parseAsync() { return Promise.resolve(); }
    }
  };
});

import { formatStockDataError } from './index';
import type { StockDataError } from '../data/twelvedata/types';

describe('formatStockDataError', () => {
  it('formats NOT_FOUND error', () => {
    const error: StockDataError = { type: 'NOT_FOUND', ticker: 'XYZ' };
    expect(formatStockDataError(error)).toBe('Ticker "XYZ" not found.');
  });

  it('formats INSUFFICIENT_DATA error', () => {
    const error: StockDataError = { 
      type: 'INSUFFICIENT_DATA', 
      ticker: 'XYZ', 
      reason: 'Missing EPS' 
    };
    expect(formatStockDataError(error)).toBe('Insufficient data for "XYZ": Missing EPS');
  });

  it('formats EMPTY_RESPONSE error', () => {
    const error: StockDataError = { 
      type: 'EMPTY_RESPONSE', 
      ticker: 'XYZ', 
      endpoint: 'quote' 
    };
    expect(formatStockDataError(error)).toBe('Empty response from "quote" for "XYZ".');
  });

  it('formats API_ERROR error', () => {
    const error: StockDataError = { 
      type: 'API_ERROR', 
      ticker: 'XYZ', 
      endpoint: 'statistics', 
      message: 'Server down' 
    };
    expect(formatStockDataError(error)).toBe('API error from "statistics" for "XYZ": Server down');
  });

  it('formats INVALID_CURRENCY_UNIT error', () => {
    const error: StockDataError = { 
      type: 'INVALID_CURRENCY_UNIT', 
      ticker: 'XYZ', 
      detail: 'Mismatched currencies' 
    };
    expect(formatStockDataError(error)).toBe('Invalid currency unit for "XYZ": Mismatched currencies');
  });
});
