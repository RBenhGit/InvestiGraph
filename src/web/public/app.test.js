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
  let handleSubmit;
  let getCurrentValuation;
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
      <input id="eps-input" readonly disabled />
      <input id="growth-input" />
      <input id="exit-pe-input" />
      <input id="required-return-input" />
      <input id="years-input" />
      <select id="mos-select"><option value="0" selected>0</option></select>
      <input id="bear-growth-input" />
      <input id="bear-exit-pe-input" value="10" />
      <input id="bear-required-return-input" value="15" />
      <input id="bull-growth-input" />
      <input id="bull-exit-pe-input" value="20" />
      <input id="bull-required-return-input" value="12" />
      <input id="notes-input" />
      <div id="rule-one-bear-fv"></div><div id="rule-one-bear-verdict"></div><div id="rule-one-bear-inputs"></div>
      <div id="rule-one-base-fv"></div><div id="rule-one-base-verdict"></div><div id="rule-one-base-inputs"></div>
      <div id="rule-one-bull-fv"></div><div id="rule-one-bull-verdict"></div><div id="rule-one-bull-inputs"></div>
      <div id="lynch-bear-fv"></div><div id="lynch-bear-verdict"></div><div id="lynch-bear-inputs"></div>
      <div id="lynch-base-fv"></div><div id="lynch-base-verdict"></div><div id="lynch-base-inputs"></div>
      <div id="lynch-bull-fv"></div><div id="lynch-bull-verdict"></div><div id="lynch-bull-inputs"></div>
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
      `${appJsCode}\nreturn { formatStockDataError, renderAnalystTable, renderHistoryTable, handleSubmit, getCurrentValuation: () => currentValuation };`
    );
    const exports = scriptExecutor(window, document);
    formatStockDataError = exports.formatStockDataError;
    renderAnalystTable = exports.renderAnalystTable;
    renderHistoryTable = exports.renderHistoryTable;
    handleSubmit = exports.handleSubmit;
    getCurrentValuation = exports.getCurrentValuation;
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

  describe('handleSubmit — locked EPS field and bear/bull growth backfill', () => {
    // Regression tests for a bug where the EPS field was locked (readonly/disabled) in the UI
    // but app.js still read its JS-assigned value back as epsOverride on the next submit, and
    // separately backfilled/saved bear/bull growth using the *clamped* value instead of the
    // raw one the base growth input uses.
    function mockValuateResponse(overrides = {}) {
      return {
        ok: true,
        ticker: 'AAPL',
        data: { ticker: 'AAPL', currentPrice: 200, currency: 'USD', epsTtm: 6.5, asOf: '2026-08-22', growth: {}, historicalPe: {} },
        effectiveEps: 6.5,
        effectiveGrowth: 40,
        analystConsensus: null,
        lynch: {
          bear: { ok: true, fairValue: 10, inputs: { epsTtm: 6.5, growthRatePercentRaw: 30, growthRatePercentClamped: 25 } },
          base: { ok: true, fairValue: 20, inputs: { epsTtm: 6.5, growthRatePercentRaw: 40, growthRatePercentClamped: 25 } },
          bull: { ok: true, fairValue: 30, inputs: { epsTtm: 6.5, growthRatePercentRaw: 50, growthRatePercentClamped: 25 } },
        },
        ruleOne: {
          bear: { ok: true, fairValue: 10, inputs: { epsTtm: 6.5, growthRatePercentRaw: 30, growthRatePercentClamped: 25, exitPeMultiple: 10, requiredReturnPercent: 15, mosPercent: 0 } },
          base: { ok: true, fairValue: 20, inputs: { epsTtm: 6.5, growthRatePercentRaw: 40, growthRatePercentClamped: 25, exitPeMultiple: 15, requiredReturnPercent: 15, mosPercent: 0 } },
          bull: { ok: true, fairValue: 30, inputs: { epsTtm: 6.5, growthRatePercentRaw: 50, growthRatePercentClamped: 25, exitPeMultiple: 20, requiredReturnPercent: 12, mosPercent: 0 } },
        },
        ...overrides,
      };
    }

    function resetForm() {
      document.getElementById('ticker-input').value = 'AAPL';
      document.getElementById('eps-input').value = '';
      document.getElementById('growth-input').value = '';
      document.getElementById('bear-growth-input').value = '';
      document.getElementById('bull-growth-input').value = '';
      document.getElementById('mos-select').value = '0';
    }

    it('never sends a stale locked EPS value back to the server as epsOverride', async () => {
      resetForm();
      let capturedBody = null;
      global.fetch = (url, opts) => {
        capturedBody = JSON.parse(opts.body);
        return Promise.resolve({ json: () => Promise.resolve(mockValuateResponse()) });
      };

      // Simulate a prior lookup having already populated the locked EPS field (as app.js
      // itself does after a successful fetch) -- this is the state a disabled input is left
      // in once JS has written to it.
      document.getElementById('eps-input').value = '999.99';

      await handleSubmit({ preventDefault() {} });

      // The key must be genuinely absent, not merely undefined -- the server treats a missing
      // epsOverride as "use data.epsTtm", which is the whole point of the locked field.
      expect(capturedBody.epsOverride).toBeUndefined();
      expect(Object.prototype.hasOwnProperty.call(capturedBody, 'epsOverride')).toBe(false);
    });

    it("does not restore a legacy record's epsOverride into the locked EPS field on Load", async () => {
      resetForm();
      global.fetch = () => Promise.resolve({ json: () => Promise.resolve(mockValuateResponse()) });

      // A legacy/CLI-saved record carrying an epsOverride. Loading it must not write that
      // value into the locked display-only field -- the live TTM EPS wins.
      renderHistoryTable([{
        id: 'legacy-1', ticker: 'AAPL', savedAt: '2026-08-01T00:00:00.000Z',
        epsTtm: 6.5, epsOverride: 42.42, years: 10,
        growthRatePercent: 12, exitPeMultiple: 15, requiredReturnPercent: 15,
        lynchFairValue: 78, ruleOneFairValue: 60,
      }]);

      const loadBtn = document.querySelector('#history-tbody .btn-action-load');
      expect(loadBtn).not.toBeNull();
      loadBtn.click();

      // Assert synchronously, before the handleSubmit() the Load handler kicks off has had a
      // chance to resolve and repaint the field with the live epsTtm. Checking after the await
      // would pass either way (handleSubmit always overwrites), which is precisely why the old
      // behaviour looked harmless -- the wrong value was only ever visible in this window.
      expect(document.getElementById('eps-input').value).not.toBe('42.42');

      await new Promise((resolve) => setTimeout(resolve, 0));
      expect(document.getElementById('eps-input').value).toBe('6.5');
    });

    it('displays the live TTM EPS after submit, overwriting whatever was there before', async () => {
      resetForm();
      document.getElementById('eps-input').value = '999.99';
      global.fetch = () => Promise.resolve({ json: () => Promise.resolve(mockValuateResponse()) });

      await handleSubmit({ preventDefault() {} });

      expect(document.getElementById('eps-input').value).toBe('6.5');
    });

    it('backfills blank bear/bull growth inputs with the raw (unclamped) growth, not the clamped one', async () => {
      resetForm();
      global.fetch = () => Promise.resolve({ json: () => Promise.resolve(mockValuateResponse()) });

      await handleSubmit({ preventDefault() {} });

      // mockValuateResponse: bear raw=30/clamped=25, bull raw=50/clamped=25.
      expect(document.getElementById('bear-growth-input').value).toBe('30');
      expect(document.getElementById('bull-growth-input').value).toBe('50');
    });

    it('saves bear/bull growthRatePercent as the raw value, matching how base is saved', async () => {
      resetForm();
      global.fetch = () => Promise.resolve({ json: () => Promise.resolve(mockValuateResponse()) });

      await handleSubmit({ preventDefault() {} });

      const saved = getCurrentValuation();
      expect(saved.base.growthRatePercent).toBe(40);
      expect(saved.bear.growthRatePercent).toBe(30);
      expect(saved.bull.growthRatePercent).toBe(50);
    });

    it('falls back to the lynch scenario\'s raw growth when ruleOne failed for that scenario', async () => {
      resetForm();
      const response = mockValuateResponse();
      response.ruleOne.bear = { ok: false, error: 'INVALID_EXIT_PE' };
      global.fetch = () => Promise.resolve({ json: () => Promise.resolve(response) });

      await handleSubmit({ preventDefault() {} });

      // lynch.bear.inputs.growthRatePercentRaw is 30 in the mock.
      expect(document.getElementById('bear-growth-input').value).toBe('30');
      expect(getCurrentValuation().bear.growthRatePercent).toBe(30);
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
