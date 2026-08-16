/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, beforeAll } from 'vitest';
import fs from 'fs';
import path from 'path';

describe('app.js frontend', () => {
  let formatStockDataError;

  beforeAll(() => {
    // Setup the DOM elements app.js expects
    document.body.innerHTML = `
      <form id="valuate-form"></form>
      <input id="ticker-input" />
      <button id="go-btn"></button>
      <input id="growth-input" />
      <input id="exit-pe-input" />
      <input id="required-return-input" />
      <input id="years-input" />
      <div id="growth-chips"></div>
      <div id="error-card"></div>
      <div id="result"></div>
      <div id="cards"></div>
      <div id="price-value"></div>
      <div id="price-meta"></div>
      <div id="price-deltas"></div>
      <div id="growth-table"></div>
      <div id="multiples-table"></div>
      <div id="analyst-table"></div>
      
      <div id="lynch-fair-value"></div>
      <div id="lynch-verdict"></div>
      <div id="lynch-inputs"></div>
      
      <div id="rule-one-fair-value"></div>
      <div id="rule-one-verdict"></div>
      <div id="rule-one-inputs"></div>
    `;

    // Load and execute app.js using new Function to capture the formatStockDataError function
    const appJsPath = path.resolve(__dirname, 'app.js');
    const appJsCode = fs.readFileSync(appJsPath, 'utf8');
    
    // Create a function that executes the script and returns the local function
    const scriptExecutor = new Function(
      'window', 'document',
      `${appJsCode}\nreturn { formatStockDataError };`
    );
    const exports = scriptExecutor(window, document);
    formatStockDataError = exports.formatStockDataError;
  });

  it('formatStockDataError handles NOT_FOUND', () => {
    const error = { type: 'NOT_FOUND', ticker: 'XYZ' };
    expect(formatStockDataError(error)).toBe('Ticker "XYZ" not found.');
  });
  
  it('formatStockDataError handles INSUFFICIENT_DATA', () => {
    const error = { type: 'INSUFFICIENT_DATA', ticker: 'XYZ', reason: 'Missing EPS' };
    expect(formatStockDataError(error)).toBe('Insufficient data for "XYZ": Missing EPS');
  });

  it('formatStockDataError handles EMPTY_RESPONSE', () => {
    const error = { type: 'EMPTY_RESPONSE', ticker: 'XYZ', endpoint: 'quote' };
    expect(formatStockDataError(error)).toBe('Empty response from "quote" for "XYZ".');
  });

  it('formatStockDataError handles API_ERROR', () => {
    const error = { type: 'API_ERROR', ticker: 'XYZ', endpoint: 'stats', message: 'Down' };
    expect(formatStockDataError(error)).toBe('API error from "stats" for "XYZ": Down');
  });

  it('formatStockDataError handles INVALID_CURRENCY_UNIT', () => {
    const error = { type: 'INVALID_CURRENCY_UNIT', ticker: 'XYZ', detail: 'Mismatch' };
    expect(formatStockDataError(error)).toBe('Invalid currency unit for "XYZ": Mismatch');
  });
});

