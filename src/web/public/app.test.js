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
  let renderPriceBanner;
  let renderGrowthTable;
  let renderMultiplesTable;
  let renderGrowthChips;
  let renderScenarioColumn;
  let renderMethodCard;
  let handleSaveValuation;
  let fetchHistory;
  let fmt;
  let fmtPercent;
  let formatDate;
  let getCurrentValuation;
  let setCurrentValuation;
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
      `${appJsCode}\nreturn { formatStockDataError, renderAnalystTable, renderHistoryTable, handleSubmit, renderPriceBanner, renderGrowthTable, renderMultiplesTable, renderGrowthChips, renderScenarioColumn, renderMethodCard, handleSaveValuation, fetchHistory, fmt, fmtPercent, formatDate, getCurrentValuation: () => currentValuation, setCurrentValuation: (v) => { currentValuation = v; } };`
    );
    const exports = scriptExecutor(window, document);
    formatStockDataError = exports.formatStockDataError;
    renderAnalystTable = exports.renderAnalystTable;
    renderHistoryTable = exports.renderHistoryTable;
    handleSubmit = exports.handleSubmit;
    renderPriceBanner = exports.renderPriceBanner;
    renderGrowthTable = exports.renderGrowthTable;
    renderMultiplesTable = exports.renderMultiplesTable;
    renderGrowthChips = exports.renderGrowthChips;
    renderScenarioColumn = exports.renderScenarioColumn;
    renderMethodCard = exports.renderMethodCard;
    handleSaveValuation = exports.handleSaveValuation;
    fetchHistory = exports.fetchHistory;
    fmt = exports.fmt;
    fmtPercent = exports.fmtPercent;
    formatDate = exports.formatDate;
    getCurrentValuation = exports.getCurrentValuation;
    setCurrentValuation = exports.setCurrentValuation;
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

  describe('renderAnalystTable — untrusted strings from the Yahoo API', () => {
    // Regression: recommendationKey is a string that arrives from a third-party API, and it
    // flowed through tableRow()'s `valueDiv.innerHTML = value` with no escaping, so markup in
    // it was parsed as live HTML rather than shown as text. Verified in jsdom: the payload
    // below produced a real <img> element carrying an onerror handler.
    function consensus(overrides = {}) {
      return {
        nextYearEpsGrowthPercent: null,
        recommendationKey: 'buy',
        priceTarget: { mean: null, high: null, low: null, numberOfAnalysts: null },
        beta: null, priceToSales: null, ruleOf40: null,
        ...overrides,
      };
    }

    it('does not build DOM elements out of markup in recommendationKey', () => {
      renderAnalystTable(consensus({ recommendationKey: '<img src=x onerror=BOOM>' }), 100);

      const table = document.getElementById('analyst-table');
      expect(table.querySelectorAll('img')).toHaveLength(0);
      // The raw text should still be visible to the user, just inert. (renderAnalystTable
      // title-cases the key, so the payload reads "<Img ..." by the time it is displayed.)
      expect(table.textContent).toMatch(/<img/i);
    });

    it('does not execute a script tag smuggled through recommendationKey', () => {
      renderAnalystTable(consensus({ recommendationKey: '<script>BOOM</script>' }), 100);

      const table = document.getElementById('analyst-table');
      expect(table.querySelectorAll('script')).toHaveLength(0);
    });

    it('still renders an ordinary recommendation normally', () => {
      renderAnalystTable(consensus({ recommendationKey: 'strong_buy' }), 100);
      expect(document.getElementById('analyst-table').textContent).toContain('Strong Buy');
    });
  });

  describe('renderPriceBanner — zero/invalid current price', () => {
    // Regression: renderPriceDelta computed (fairValue / currentPrice - 1) * 100 with no guard
    // on currentPrice. parseNumber deliberately treats a real 0 as a value (not missing) and
    // fetchStockData only rejects null, so a "0.00" close price reaches the renderer and
    // produces Infinity -- displayed to the user as a "+Infinity%" upside.
    function bannerData(currentPrice) {
      return { ticker: 'AAPL', currentPrice, currency: 'USD', epsTtm: 6.5, asOf: '2026-08-22' };
    }

    it('renders n/a rather than Infinity% when the current price is zero', () => {
      renderPriceBanner(bannerData(0), { ok: true, fairValue: 50 }, { ok: true, fairValue: 40 });

      const text = document.getElementById('price-deltas').textContent;
      expect(text).not.toMatch(/Infinity/);
      expect(text).toMatch(/n\/a/);
    });

    it('renders analyst price targets without a delta when the price is zero', () => {
      // Same guard, second site: priceTargetValue() feeds the analyst table's target rows.
      renderAnalystTable(
        { nextYearEpsGrowthPercent: null, recommendationKey: 'buy',
          priceTarget: { mean: 250, high: 300, low: 200, numberOfAnalysts: 40 },
          beta: null, priceToSales: null, ruleOf40: null },
        0,
      );

      const text = document.getElementById('analyst-table').textContent;
      expect(text).not.toMatch(/Infinity/);
      expect(text).toMatch(/250\.00/);
    });

    it('still renders a real percentage for a normal price', () => {
      renderPriceBanner(bannerData(100), { ok: true, fairValue: 150 }, { ok: true, fairValue: 50 });

      const text = document.getElementById('price-deltas').textContent;
      expect(text).not.toMatch(/Infinity|n\/a/);
      expect(text).toMatch(/\+50\.00%/);
      expect(text).toMatch(/-50\.00%/);
    });
  });

  describe('fmt / fmtPercent / formatDate', () => {
    it('renders n/a for null and undefined, but a real 0 as a value', () => {
      expect(fmt(null)).toBe('n/a');
      expect(fmt(undefined)).toBe('n/a');
      expect(fmt(0)).toBe('0.00');
      expect(fmtPercent(null)).toBe('n/a');
      expect(fmtPercent(0)).toBe('0.00%');
      expect(fmt(12.345)).toBe('12.35');
      expect(fmtPercent(-4.5)).toBe('-4.50%');
    });

    it('formatDate returns n/a for empty input and formats a real ISO string', () => {
      expect(formatDate('')).toBe('n/a');
      expect(formatDate(null)).toBe('n/a');
      expect(formatDate('2026-08-22T14:30:00.000Z')).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/);
    });
  });

  describe('renderGrowthTable', () => {
    const growth = {
      historical1yPercent: 10,
      historical3yPercent: 20,
      historical5yPercent: null,
      analystEstimate5yPercent: -5,
    };

    it('renders one row per source, with n/a for missing ones', () => {
      renderGrowthTable(growth, 20);
      const rows = document.getElementById('growth-table').querySelectorAll('.mini-row');
      expect(rows).toHaveLength(4);
      const text = document.getElementById('growth-table').textContent;
      expect(text).toContain('Historical, 1Y');
      expect(text).toContain('10.00%');
      expect(text).toContain('n/a');
      expect(text).toContain('-5.00%');
    });

    it('highlights exactly the source matching growthUsed', () => {
      renderGrowthTable(growth, 20);
      const active = document.getElementById('growth-table').querySelectorAll('.mini-row-active');
      expect(active).toHaveLength(1);
      expect(active[0].textContent).toContain('Historical, 3Y');
    });

    it('sizes bar fill by magnitude relative to the largest absolute value', () => {
      renderGrowthTable(growth, 20);
      const rows = document.getElementById('growth-table').querySelectorAll('.mini-row');
      // max magnitude is 20 (the 3Y source); 1Y is 10 -> 0.5, analyst is -5 -> 0.25 (abs).
      expect(rows[0].style.getPropertyValue('--bar-fill')).toBe('0.5');
      expect(rows[1].style.getPropertyValue('--bar-fill')).toBe('1');
      expect(rows[3].style.getPropertyValue('--bar-fill')).toBe('0.25');
    });

    it('does not divide by zero when every source is null', () => {
      renderGrowthTable(
        { historical1yPercent: null, historical3yPercent: null, historical5yPercent: null, analystEstimate5yPercent: null },
        null,
      );
      const text = document.getElementById('growth-table').textContent;
      expect(text).not.toMatch(/NaN|Infinity/);
      expect(document.getElementById('growth-table').querySelectorAll('.mini-row')).toHaveLength(4);
      expect(document.getElementById('growth-table').querySelectorAll('.mini-row-active')).toHaveLength(0);
    });

    it('highlights nothing when growthUsed matches no source', () => {
      renderGrowthTable(growth, 99);
      expect(document.getElementById('growth-table').querySelectorAll('.mini-row-active')).toHaveLength(0);
    });
  });

  describe('renderMultiplesTable', () => {
    function multiplesData(overrides = {}) {
      return {
        ticker: 'AAPL', currentPrice: 100, currency: 'USD', epsTtm: 5, asOf: '2026-08-22',
        historicalPe: { avg1y: 20, avg3y: 22, avg5y: 25 },
        ...overrides,
      };
    }

    it('computes trailing P/E from the effective EPS, not always epsTtm', () => {
      renderMultiplesTable(multiplesData(), 10, 4, null);
      // price 100 / effectiveEps 4 = 25.00
      expect(document.getElementById('multiples-table').textContent).toContain('25.00');
    });

    it('falls back to epsTtm when effectiveEps is null', () => {
      renderMultiplesTable(multiplesData(), 10, null, null);
      // price 100 / epsTtm 5 = 20.00
      expect(document.getElementById('multiples-table').textContent).toContain('20.00');
    });

    it('renders PEG without Infinity when growth is zero or negative', () => {
      renderMultiplesTable(multiplesData(), 0, 5, null);
      expect(document.getElementById('multiples-table').textContent).not.toMatch(/Infinity|NaN/);
      renderMultiplesTable(multiplesData(), -3, 5, null);
      expect(document.getElementById('multiples-table').textContent).not.toMatch(/Infinity|NaN/);
    });

    it('renders trailing P/E without Infinity when EPS is zero or negative', () => {
      renderMultiplesTable(multiplesData({ epsTtm: 0 }), 10, null, null);
      expect(document.getElementById('multiples-table').textContent).not.toMatch(/Infinity|NaN/);
      renderMultiplesTable(multiplesData({ epsTtm: -2 }), 10, null, null);
      expect(document.getElementById('multiples-table').textContent).not.toMatch(/Infinity|NaN/);
    });

    it('appends the P/S row only when analyst data carries one', () => {
      renderMultiplesTable(multiplesData(), 10, 5, null);
      expect(document.getElementById('multiples-table').textContent).not.toContain('P/S ratio');

      renderMultiplesTable(multiplesData(), 10, 5, { priceToSales: 9.65 });
      expect(document.getElementById('multiples-table').textContent).toContain('P/S ratio');
    });

    it('does not render a P/S row for a null priceToSales', () => {
      renderMultiplesTable(multiplesData(), 10, 5, { priceToSales: null });
      expect(document.getElementById('multiples-table').textContent).not.toContain('P/S ratio');
    });
  });

  describe('renderGrowthChips', () => {
    it('renders a chip per available source and skips null ones', () => {
      renderGrowthChips({
        historical1yPercent: 10, historical3yPercent: null,
        historical5yPercent: 8, analystEstimate5yPercent: null,
      });
      const chips = document.getElementById('growth-chips').querySelectorAll('.chip');
      expect(chips).toHaveLength(2);
      expect(chips[0].textContent).toBe('1Y: 10.00%');
      expect(chips[1].textContent).toBe('5Y hist: 8.00%');
    });

    it('writes the chip value into the growth input when clicked', () => {
      document.getElementById('growth-input').value = '';
      renderGrowthChips({
        historical1yPercent: 12.345, historical3yPercent: null,
        historical5yPercent: null, analystEstimate5yPercent: null,
      });
      document.getElementById('growth-chips').querySelector('.chip').click();
      expect(document.getElementById('growth-input').value).toBe('12.35');
    });

    it('renders a chip for a real 0 rather than skipping it', () => {
      renderGrowthChips({
        historical1yPercent: 0, historical3yPercent: null,
        historical5yPercent: null, analystEstimate5yPercent: null,
      });
      const chips = document.getElementById('growth-chips').querySelectorAll('.chip');
      expect(chips).toHaveLength(1);
      expect(chips[0].textContent).toBe('1Y: 0.00%');
    });
  });

  describe('renderScenarioColumn / renderMethodCard', () => {
    const okResult = {
      ok: true, fairValue: 150,
      inputs: { epsTtm: 6, growthRatePercentRaw: 40, growthRatePercentClamped: 25 },
    };

    it('shows the fair value and an Undervalued verdict when above the price', () => {
      renderScenarioColumn('lynch', 'base', okResult, 100);
      expect(document.getElementById('lynch-base-fv').textContent).toBe('150.00');
      expect(document.getElementById('lynch-base-verdict').textContent).toBe('Undervalued');
      expect(document.getElementById('lynch-base-verdict').className).toContain('good');
    });

    it('shows Overvalued when the fair value is below the price', () => {
      renderScenarioColumn('lynch', 'base', okResult, 200);
      expect(document.getElementById('lynch-base-verdict').textContent).toBe('Overvalued');
      expect(document.getElementById('lynch-base-verdict').className).toContain('bad');
    });

    it('surfaces the error code and clears inputs on a failed scenario', () => {
      renderScenarioColumn('lynch', 'bear', { ok: false, error: 'MISSING_GROWTH_RATE' }, 100);
      expect(document.getElementById('lynch-bear-fv').textContent).toBe('n/a');
      expect(document.getElementById('lynch-bear-verdict').textContent).toBe('FAILED (MISSING_GROWTH_RATE)');
      expect(document.getElementById('lynch-bear-inputs').innerHTML).toBe('');
    });

    it('shows both raw and clamped growth when the clamp actually applied', () => {
      renderScenarioColumn('lynch', 'base', okResult, 100);
      const html = document.getElementById('lynch-base-inputs').innerHTML;
      expect(html).toContain('40.00%');
      expect(html).toContain('25.00%');
    });

    it('shows a single growth figure when no clamping occurred', () => {
      renderScenarioColumn('lynch', 'base', {
        ok: true, fairValue: 120,
        inputs: { epsTtm: 6, growthRatePercentRaw: 20, growthRatePercentClamped: 20 },
      }, 100);
      const html = document.getElementById('lynch-base-inputs').innerHTML;
      expect(html).toContain('growth:');
      expect(html).toContain('20.00%');
    });

    it('renderMethodCard fills all three scenario columns', () => {
      renderMethodCard('rule-one', { bear: okResult, base: okResult, bull: okResult }, 100);
      expect(document.getElementById('rule-one-bear-fv').textContent).toBe('150.00');
      expect(document.getElementById('rule-one-base-fv').textContent).toBe('150.00');
      expect(document.getElementById('rule-one-bull-fv').textContent).toBe('150.00');
    });

    it('renderMethodCard passes per-scenario extras through to each column', () => {
      renderMethodCard('rule-one', { bear: okResult, base: okResult, bull: okResult }, 100,
        (name) => [['exit P/E', name === 'bear' ? '10' : '20']]);
      expect(document.getElementById('rule-one-bear-inputs').innerHTML).toContain('10');
      expect(document.getElementById('rule-one-bull-inputs').innerHTML).toContain('20');
    });
  });

  describe('fetchHistory', () => {
    it('requests the unfiltered endpoint when no filter is given', async () => {
      let calledUrl = null;
      global.fetch = (url) => {
        calledUrl = url;
        return Promise.resolve({ json: () => Promise.resolve({ ok: true, data: [] }) });
      };
      await fetchHistory('');
      expect(calledUrl).toBe('/api/history');
    });

    it('url-encodes a ticker filter', async () => {
      let calledUrl = null;
      global.fetch = (url) => {
        calledUrl = url;
        return Promise.resolve({ json: () => Promise.resolve({ ok: true, data: [] }) });
      };
      await fetchHistory('BRK B&');
      expect(calledUrl).toBe('/api/history?ticker=BRK%20B%26');
    });

    it('swallows a rejected fetch without throwing', async () => {
      global.fetch = () => Promise.reject(new Error('network down'));
      await expect(fetchHistory('')).resolves.toBeUndefined();
    });

    it('does not render when the response is not ok', async () => {
      global.fetch = () => Promise.resolve({ json: () => Promise.resolve({ ok: false }) });
      document.getElementById('history-tbody').innerHTML = '<tr id="sentinel"></tr>';
      await fetchHistory('');
      expect(document.getElementById('sentinel')).not.toBeNull();
    });
  });

  describe('handleSaveValuation', () => {
    it('does nothing when there is no current valuation', async () => {
      setCurrentValuation(null);
      let called = false;
      global.fetch = () => { called = true; return Promise.resolve({ ok: true, json: () => Promise.resolve({ ok: true }) }); };
      await handleSaveValuation();
      expect(called).toBe(false);
    });

    it('posts the current valuation and reports success', async () => {
      setCurrentValuation({ ticker: 'AAPL', years: 10 });
      document.getElementById('notes-input').value = '  my thesis  ';
      const calls = [];
      global.fetch = (url, opts) => {
        calls.push([url, opts]);
        if (opts && opts.method === 'POST') {
          return Promise.resolve({ ok: true, json: () => Promise.resolve({ ok: true }) });
        }
        return Promise.resolve({ json: () => Promise.resolve({ ok: true, data: [] }) });
      };

      await handleSaveValuation();

      const post = calls.find(([, o]) => o && o.method === 'POST');
      expect(post).toBeDefined();
      expect(JSON.parse(post[1].body).notes).toBe('my thesis');
      expect(document.getElementById('save-status').textContent).toContain('saved');
      expect(document.getElementById('save-btn').disabled).toBe(false);
    });

    it('surfaces a server-side failure message and re-enables the button', async () => {
      setCurrentValuation({ ticker: 'AAPL', years: 10 });
      global.fetch = () => Promise.resolve({ ok: false, json: () => Promise.resolve({ ok: false, error: { message: 'disk full' } }) });

      await handleSaveValuation();

      expect(document.getElementById('save-status').textContent).toBe('disk full');
      expect(document.getElementById('save-status').className).toContain('bad');
      expect(document.getElementById('save-btn').disabled).toBe(false);
    });

    it('surfaces a thrown network error and re-enables the button', async () => {
      setCurrentValuation({ ticker: 'AAPL', years: 10 });
      global.fetch = () => Promise.reject(new Error('offline'));

      await handleSaveValuation();

      expect(document.getElementById('save-status').textContent).toContain('offline');
      expect(document.getElementById('save-status').className).toContain('bad');
      expect(document.getElementById('save-btn').disabled).toBe(false);
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
