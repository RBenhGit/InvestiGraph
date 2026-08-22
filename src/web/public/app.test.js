/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, beforeAll } from 'vitest';
import fs from 'fs';
import path from 'path';

describe('app.js frontend', () => {
  let formatStockDataError;
  let renderAnalystTable;
  let renderHistoryTable;
  let analystTableEl;
  let historyTbodyEl;
  let historyEmptyEl;
  let historyTableContainerEl;

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
      `${appJsCode}\nreturn { formatStockDataError, renderAnalystTable, renderHistoryTable };`
    );
    const exports = scriptExecutor(window, document);
    formatStockDataError = exports.formatStockDataError;
    renderAnalystTable = exports.renderAnalystTable;
    renderHistoryTable = exports.renderHistoryTable;
    analystTableEl = document.getElementById('analyst-table');
    historyTbodyEl = document.getElementById('history-tbody');
    historyEmptyEl = document.getElementById('history-empty');
    historyTableContainerEl = document.getElementById('history-table-container');
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

  describe('renderHistoryTable — legacy vs. 3-scenario (base/bear/bull) record shapes', () => {
    function legacyRecord(overrides = {}) {
      return {
        id: '1',
        ticker: 'AAPL',
        evaluatedAt: '2026-08-19T10:00:00.000Z',
        currentPrice: 220,
        currency: 'USD',
        years: 5,
        growthRatePercent: 12,
        exitPeMultiple: 25,
        requiredReturnPercent: 15,
        mosPercent: 25,
        lynchFairValue: 156,
        ruleOneFairValue: 180,
        notes: '',
        ...overrides,
      };
    }

    function scenario(overrides = {}) {
      return {
        growthRatePercent: 10,
        exitPeMultiple: 15,
        requiredReturnPercent: 15,
        mosPercent: 25,
        lynchFairValue: 100,
        ruleOneFairValue: 110,
        ...overrides,
      };
    }

    it('renders exactly one row for a legacy (pre-scenario) record', () => {
      renderHistoryTable([legacyRecord()]);
      const rows = historyTbodyEl.querySelectorAll('tr');
      expect(rows.length).toBe(1);
      expect(historyEmptyEl.hidden).toBe(true);
      expect(historyTableContainerEl.hidden).toBe(false);
      // Legacy records have no scenario badge — a single, un-labelled row.
      expect(historyTbodyEl.querySelector('.badge-scenario')).toBeNull();
    });

    it('renders exactly three rows (Bear/Base/Bull), each labelled, for a full scenario record', () => {
      const record = {
        id: '2',
        ticker: 'NVDA',
        evaluatedAt: '2026-08-22T10:00:00.000Z',
        currentPrice: 300,
        currency: 'USD',
        years: 10,
        notes: 'test',
        base: scenario({ ruleOneFairValue: 110 }),
        bear: scenario({ exitPeMultiple: 8, ruleOneFairValue: 60 }),
        bull: scenario({ exitPeMultiple: 22, ruleOneFairValue: 180 }),
      };
      renderHistoryTable([record]);
      const rows = historyTbodyEl.querySelectorAll('tr');
      expect(rows.length).toBe(3);
      const labels = Array.from(historyTbodyEl.querySelectorAll('.badge-scenario')).map((el) => el.textContent);
      expect(labels).toEqual(['Bear', 'Base', 'Bull']);
      // Date/Price/Notes/Actions only render on the first row, with rowSpan covering the rest.
      expect(rows[0].querySelector('.table-date').rowSpan).toBe(3);
      expect(rows[1].querySelector('.table-date')).toBeNull();
      expect(rows[2].querySelector('.table-date')).toBeNull();
    });

    it('falls back to the base scenario for a missing bear or bull (item.bear || item.base)', () => {
      const record = {
        id: '3',
        ticker: 'MSFT',
        evaluatedAt: '2026-08-22T11:00:00.000Z',
        currentPrice: 400,
        currency: 'USD',
        years: 10,
        base: scenario({ ruleOneFairValue: 420 }),
        // bear/bull deliberately omitted
      };
      renderHistoryTable([record]);
      const rows = historyTbodyEl.querySelectorAll('tr');
      expect(rows.length).toBe(3);
      // Bear and Bull rows both fall back to base's fair value (420) since neither was provided.
      const ruleOneCells = Array.from(rows).map((r) => r.querySelectorAll('.table-val')[0].textContent);
      expect(ruleOneCells[0]).toContain('420');
      expect(ruleOneCells[1]).toContain('420');
      expect(ruleOneCells[2]).toContain('420');
    });

    it('shows the empty state and hides the table when there are no records', () => {
      renderHistoryTable([]);
      expect(historyEmptyEl.hidden).toBe(false);
      expect(historyTableContainerEl.hidden).toBe(true);
      expect(historyTbodyEl.innerHTML).toBe('');
    });
  });
});
