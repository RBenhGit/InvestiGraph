/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, beforeAll } from 'vitest';
import fs from 'fs';
import path from 'path';

describe('app.js frontend', () => {
  let formatStockDataError;
  let renderAnalystTable;
  let analystTableEl;

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
      <select id="mos-select"></select>
      <input id="notes-input" />
      <button class="scenario-btn" data-scenario="bear"></button>
      <button class="scenario-btn" data-scenario="base"></button>
      <button class="scenario-btn" data-scenario="bull"></button>
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

      <button id="save-btn"></button>
      <span id="save-status"></span>
      <div id="history-empty"></div>
      <div id="history-table-container"></div>
      <table>
        <tbody id="history-tbody"></tbody>
      </table>
      <input id="history-filter" />
      <button id="history-refresh-btn"></button>
    `;

    // Mock fetch for initial fetchHistory
    global.fetch = () => Promise.resolve({
      json: () => Promise.resolve({ ok: true, data: [] }),
    });

    // Load and execute app.js using new Function to capture the formatStockDataError function
    const appJsPath = path.resolve(__dirname, 'app.js');
    const appJsCode = fs.readFileSync(appJsPath, 'utf8');
    
    // Create a function that executes the script and returns the local function
    const scriptExecutor = new Function(
      'window', 'document',
      `${appJsCode}\nreturn { formatStockDataError, renderAnalystTable };`
    );
    const exports = scriptExecutor(window, document);
    formatStockDataError = exports.formatStockDataError;
    renderAnalystTable = exports.renderAnalystTable;
    analystTableEl = document.getElementById('analyst-table');
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

  describe('renderAnalystTable — Financial Health section', () => {
    function baseConsensus(overrides = {}) {
      return {
        nextYearEpsGrowthPercent: 10,
        priceTarget: { mean: 100, high: 120, low: 80, numberOfAnalysts: 5 },
        recommendationKey: 'buy',
        beta: null,
        priceToSales: null,
        ruleOf40: null,
        ...overrides,
      };
    }

    it('renders both Rule of 40 and Beta rows, with correct values, when both are present', () => {
      renderAnalystTable(baseConsensus({ beta: 1.23, ruleOf40: 45.67 }), 100);
      const text = analystTableEl.textContent;
      expect(text).toContain('Financial Health');
      expect(text).toContain('Rule of 40');
      expect(text).toContain('45.67%');
      expect(text).toContain('Beta (Volatility)');
      expect(text).toContain('1.23');
    });

    it('renders only the Rule of 40 row (not Beta) when only ruleOf40 is present', () => {
      renderAnalystTable(baseConsensus({ beta: null, ruleOf40: 52.38 }), 100);
      const text = analystTableEl.textContent;
      expect(text).toContain('Financial Health');
      expect(text).toContain('Rule of 40');
      expect(text).not.toContain('Beta (Volatility)');
    });

    it('does NOT render the Financial Health header at all when both beta and ruleOf40 are null', () => {
      // Regression test: beta/ruleOf40 are typed `number | null`, never `undefined` — the
      // section header must gate on `!== null`, not `!== undefined`, or it renders an empty
      // header for every ticker Yahoo has no financial-health coverage for.
      renderAnalystTable(baseConsensus({ beta: null, ruleOf40: null }), 100);
      const text = analystTableEl.textContent;
      expect(text).not.toContain('Financial Health');
      expect(text).not.toContain('Rule of 40');
      expect(text).not.toContain('Beta (Volatility)');
    });
  });
});
