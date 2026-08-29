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
  let renderVerdict;
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
      <button id="refresh-btn"></button>
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
      <select id="evaluator-select">
        <option value="Aviv" selected>Aviv</option>
        <option value="Bob">Bob</option>
      </select>
    `;

    // Mock fetch for initial fetchHistory
    global.fetch = () =>
      Promise.resolve({
        json: () => Promise.resolve({ ok: true, data: [] }),
      });

    // Load and execute app.js using new Function to capture the formatStockDataError function
    const appJsPath = path.resolve(__dirname, 'app.js');
    const appJsCode = fs.readFileSync(appJsPath, 'utf8');

    // Create a function that executes the script and returns the local function
    const scriptExecutor = new Function(
      'window',
      'document',
      `${appJsCode}\nreturn { formatStockDataError, renderAnalystTable, renderHistoryTable, handleSubmit, renderPriceBanner, renderGrowthTable, renderMultiplesTable, renderGrowthChips, renderScenarioColumn, renderMethodCard, handleSaveValuation, fetchHistory, fmt, fmtPercent, formatDate, renderVerdict, getCurrentValuation: () => currentValuation, setCurrentValuation: (v) => { currentValuation = v; } };`,
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
    renderVerdict = exports.renderVerdict;
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

    it('tags a plausible Rule of 40 (>= 40) as good', () => {
      renderAnalystTable(baseConsensus({ ruleOf40: 45.67 }), 100);
      const badge = analystTableEl.querySelector('.health-badge');
      expect(badge.classList.contains('good')).toBe(true);
    });

    it('tags a borderline Rule of 40 (20-39.99) as warning', () => {
      renderAnalystTable(baseConsensus({ ruleOf40: 28 }), 100);
      const badge = analystTableEl.querySelector('.health-badge');
      expect(badge.classList.contains('warning')).toBe(true);
    });

    it('tags a weak Rule of 40 (< 20) as bad', () => {
      renderAnalystTable(baseConsensus({ ruleOf40: 12 }), 100);
      const badge = analystTableEl.querySelector('.health-badge');
      expect(badge.classList.contains('bad')).toBe(true);
    });

    it('tags an implausibly high Rule of 40 (>= 100) as bad, not good — values in this range are far more likely a data artifact than a real score (live-confirmed: NVDA/PLTR/ANET all land well above 40 and below 100 once period-matched; an unmatched-period figure like the pre-fix IONQ case of 286.80 or NVDA of 150.49 should read as suspicious, not excellent)', () => {
      renderAnalystTable(baseConsensus({ ruleOf40: 130.77 }), 100);
      const badge = analystTableEl.querySelector('.health-badge');
      expect(badge.classList.contains('bad')).toBe(true);
      expect(badge.classList.contains('good')).toBe(false);
    });

    it('tags exactly 100 as bad (boundary is inclusive)', () => {
      renderAnalystTable(baseConsensus({ ruleOf40: 100 }), 100);
      const badge = analystTableEl.querySelector('.health-badge');
      expect(badge.classList.contains('bad')).toBe(true);
    });

    it('tags 99.99 as good, just under the implausible-high boundary', () => {
      renderAnalystTable(baseConsensus({ ruleOf40: 99.99 }), 100);
      const badge = analystTableEl.querySelector('.health-badge');
      expect(badge.classList.contains('good')).toBe(true);
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
        data: {
          ticker: 'AAPL',
          currentPrice: 200,
          currency: 'USD',
          epsTtm: 6.5,
          asOf: '2026-08-22',
          growth: {},
          historicalPe: {},
        },
        effectiveEps: 6.5,
        effectiveGrowth: 40,
        bearGrowth: 30,
        bullGrowth: 50,
        analystConsensus: null,
        ruleOne: {
          bear: {
            ok: true,
            fairValue: 10,
            inputs: {
              epsTtm: 6.5,
              growthRatePercentRaw: 30,
              growthRatePercentClamped: 25,
              exitPeMultiple: 10,
              requiredReturnPercent: 15,
              mosPercent: 0,
            },
          },
          base: {
            ok: true,
            fairValue: 20,
            inputs: {
              epsTtm: 6.5,
              growthRatePercentRaw: 40,
              growthRatePercentClamped: 25,
              exitPeMultiple: 15,
              requiredReturnPercent: 15,
              mosPercent: 0,
            },
          },
          bull: {
            ok: true,
            fairValue: 30,
            inputs: {
              epsTtm: 6.5,
              growthRatePercentRaw: 50,
              growthRatePercentClamped: 25,
              exitPeMultiple: 20,
              requiredReturnPercent: 12,
              mosPercent: 0,
            },
          },
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
      renderHistoryTable([
        {
          id: 'legacy-1',
          ticker: 'AAPL',
          savedAt: '2026-08-01T00:00:00.000Z',
          epsTtm: 6.5,
          epsOverride: 42.42,
          years: 10,
          growthRatePercent: 12,
          exitPeMultiple: 15,
          requiredReturnPercent: 15,
          ruleOneFairValue: 60,
        },
      ]);

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

    it('backfills bear growth from body.bearGrowth even when ruleOne failed for that scenario', async () => {
      resetForm();
      const response = mockValuateResponse();
      response.ruleOne.bear = { ok: false, error: 'INVALID_EXIT_PE' };
      global.fetch = () => Promise.resolve({ json: () => Promise.resolve(response) });

      await handleSubmit({ preventDefault() {} });

      // response.bearGrowth is 30 in the mock -- the server always echoes the value it actually
      // used, independent of whether ruleOne succeeded for that scenario.
      expect(document.getElementById('bear-growth-input').value).toBe('30');
      expect(getCurrentValuation().bear.growthRatePercent).toBe(30);
    });

    it('backfills bear growth from body.bearGrowth even when the scenario fails', async () => {
      // Regression: the old logic derived bear/bull growth from ruleOne.bear.inputs -- which does
      // not exist on a failed ValuationResult. When ruleOne fails on an unrelated
      // INVALID_EXIT_PE, the old code silently produced null even though a specific bearGrowth
      // number was actually used server-side.
      resetForm();
      const response = mockValuateResponse();
      response.bearGrowth = -5;
      response.ruleOne.bear = { ok: false, error: 'INVALID_EXIT_PE' };
      global.fetch = () => Promise.resolve({ json: () => Promise.resolve(response) });

      await handleSubmit({ preventDefault() {} });

      expect(document.getElementById('bear-growth-input').value).toBe('-5');
      expect(getCurrentValuation().bear.growthRatePercent).toBe(-5);
    });
  });

  describe('handleSubmit — concurrent requests', () => {
    // The Go button is disabled while a request is in flight, but the "Refresh Live" button is
    // not, and nothing sequences responses. Two overlapping lookups therefore race: whichever
    // response arrives LAST wins the DOM, even if it belongs to the EARLIER request. A user who
    // types AAPL, hits Go, then switches to MSFT and hits Go again can be shown MSFT's price
    // banner with AAPL's fair values, or vice versa, with no indication anything is wrong.
    function responseFor(ticker, epsTtm, fairValue) {
      return {
        ok: true,
        ticker,
        data: {
          ticker,
          currentPrice: 100,
          currency: 'USD',
          epsTtm,
          asOf: '2026-08-22',
          growth: {},
          historicalPe: {},
        },
        effectiveEps: epsTtm,
        effectiveGrowth: 10,
        analystConsensus: null,
        ruleOne: {
          bear: {
            ok: true,
            fairValue,
            inputs: {
              epsTtm,
              growthRatePercentRaw: 10,
              growthRatePercentClamped: 10,
              exitPeMultiple: 10,
              requiredReturnPercent: 15,
              mosPercent: 0,
            },
          },
          base: {
            ok: true,
            fairValue,
            inputs: {
              epsTtm,
              growthRatePercentRaw: 10,
              growthRatePercentClamped: 10,
              exitPeMultiple: 15,
              requiredReturnPercent: 15,
              mosPercent: 0,
            },
          },
          bull: {
            ok: true,
            fairValue,
            inputs: {
              epsTtm,
              growthRatePercentRaw: 10,
              growthRatePercentClamped: 10,
              exitPeMultiple: 20,
              requiredReturnPercent: 12,
              mosPercent: 0,
            },
          },
        },
      };
    }

    it('ignores a slow earlier response once a newer request has been issued', async () => {
      document.getElementById('ticker-input').value = 'AAPL';
      document.getElementById('growth-input').value = '';
      document.getElementById('bear-growth-input').value = '';
      document.getElementById('bull-growth-input').value = '';

      let resolveFirst;
      const firstBody = new Promise((resolve) => {
        resolveFirst = resolve;
      });
      let call = 0;
      global.fetch = () => {
        call += 1;
        // First call resolves late (slow network); second resolves immediately.
        return call === 1
          ? Promise.resolve({ json: () => firstBody })
          : Promise.resolve({ json: () => Promise.resolve(responseFor('MSFT', 12, 999)) });
      };

      // Kick off the slow AAPL lookup, then immediately start the MSFT one -- exactly what the
      // always-enabled Refresh button allows.
      const slow = handleSubmit({ preventDefault() {} });
      document.getElementById('ticker-input').value = 'MSFT';
      await handleSubmit({ preventDefault() {} });

      // MSFT has landed and owns the DOM.
      expect(document.getElementById('eps-input').value).toBe('12');
      expect(getCurrentValuation().ticker).toBe('MSFT');

      // Now the stale AAPL response finally arrives. It must NOT overwrite MSFT.
      resolveFirst(responseFor('AAPL', 6.5, 111));
      await slow;

      expect(getCurrentValuation().ticker).toBe('MSFT');
      expect(document.getElementById('eps-input').value).toBe('12');
    });
  });

  describe('setLoading — Refresh Live button', () => {
    // Regression: setLoading disables "Refresh Live" alongside "Go" while a request is in
    // flight (leaving it enabled is what let two overlapping lookups race in the first place),
    // but no test ever exercised this because the DOM fixture had no #refresh-btn element --
    // document.getElementById('refresh-btn') was always null, so this whole mechanism could be
    // deleted without failing anything.
    it('disables the Refresh Live button while a request is in flight, and re-enables it after', async () => {
      document.getElementById('ticker-input').value = 'AAPL';
      let resolveFetch;
      global.fetch = () =>
        new Promise((resolve) => {
          resolveFetch = resolve;
        });

      const pending = handleSubmit({ preventDefault() {} });
      expect(document.getElementById('refresh-btn').disabled).toBe(true);

      resolveFetch({
        json: () => Promise.resolve({ ok: false, error: { type: 'NOT_FOUND', ticker: 'AAPL' } }),
      });
      await pending;

      expect(document.getElementById('refresh-btn').disabled).toBe(false);
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
        beta: null,
        priceToSales: null,
        ruleOf40: null,
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
      renderPriceBanner(bannerData(0), { ok: true, fairValue: 40 });

      const text = document.getElementById('price-deltas').textContent;
      expect(text).not.toMatch(/Infinity/);
      expect(text).toMatch(/n\/a/);
    });

    it('renders analyst price targets without a delta when the price is zero', () => {
      // Same guard, second site: priceTargetValue() feeds the analyst table's target rows.
      renderAnalystTable(
        {
          nextYearEpsGrowthPercent: null,
          recommendationKey: 'buy',
          priceTarget: { mean: 250, high: 300, low: 200, numberOfAnalysts: 40 },
          beta: null,
          priceToSales: null,
          ruleOf40: null,
        },
        0,
      );

      const text = document.getElementById('analyst-table').textContent;
      expect(text).not.toMatch(/Infinity/);
      expect(text).toMatch(/250\.00/);
    });

    it('still renders a real percentage for a normal price', () => {
      renderPriceBanner(bannerData(100), { ok: true, fairValue: 150 });

      const text = document.getElementById('price-deltas').textContent;
      expect(text).not.toMatch(/Infinity|n\/a/);
      expect(text).toMatch(/\+50\.00%/);
    });
  });

  describe('renderPriceBanner — epsSource labeling', () => {
    // effectiveEps/epsSource/epsSourceDetail come from the server's resolveEpsWithFallback
    // (src/data/resolveEps.ts) -- these tests pin the label text so a Yahoo-sourced EPS is never
    // silently shown as if it were Twelve Data's raw figure.
    function bannerData(overrides = {}) {
      return {
        ticker: 'CSCO',
        currentPrice: 110.23,
        currency: 'USD',
        epsTtm: 3.08,
        asOf: '2026-08-25T08:48:18.421Z',
        staleTtmWarning: false,
        ...overrides,
      };
    }

    it('shows no source note and no warning class for a healthy (non-stale) figure', () => {
      renderPriceBanner(
        bannerData({ staleTtmWarning: false }),
        { ok: true, fairValue: 40 },
        3.08,
        'twelvedata',
        'Twelve Data, as of 2026-08-25T08:48:18.421Z',
      );

      const meta = document.getElementById('price-meta');
      expect(meta.textContent).toContain('EPS (TTM) 3.08');
      expect(meta.textContent).not.toMatch(/Yahoo|stale/i);
      expect(meta.classList.contains('stale-warning')).toBe(false);
      expect(meta.classList.contains('eps-fallback-note')).toBe(false);
    });

    it('shows the Yahoo-fallback EPS value and note, not the stale Twelve Data figure', () => {
      renderPriceBanner(
        bannerData({ epsTtm: 3.08, staleTtmWarning: true }),
        { ok: true, fairValue: 9.48 },
        3.31,
        'yahoo-fallback',
        "Yahoo Finance, as of 2026-08-25T08:48:20.617Z — used because Twelve Data's figure ($3.08) looked stale",
      );

      const meta = document.getElementById('price-meta');
      expect(meta.textContent).toContain('EPS (TTM) 3.31');
      expect(meta.textContent).not.toContain('3.08');
      expect(meta.textContent).toMatch(/Yahoo Finance/);
      expect(meta.classList.contains('eps-fallback-note')).toBe(true);
      expect(meta.classList.contains('stale-warning')).toBe(false);
      expect(meta.title).toContain('Yahoo Finance');
    });

    it('shows a warning (not the fallback note) when stale and the Yahoo fallback was unavailable', () => {
      renderPriceBanner(
        bannerData({ epsTtm: 3.08, staleTtmWarning: true }),
        { ok: true, fairValue: 8.82 },
        3.08,
        'twelvedata-stale-no-fallback',
        undefined,
      );

      const meta = document.getElementById('price-meta');
      expect(meta.textContent).toContain('EPS (TTM) 3.08');
      expect(meta.textContent).toMatch(/stale/i);
      expect(meta.textContent).toMatch(/unavailable/i);
      expect(meta.classList.contains('stale-warning')).toBe(true);
      expect(meta.classList.contains('eps-fallback-note')).toBe(false);
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
        {
          historical1yPercent: null,
          historical3yPercent: null,
          historical5yPercent: null,
          analystEstimate5yPercent: null,
        },
        null,
      );
      const text = document.getElementById('growth-table').textContent;
      expect(text).not.toMatch(/NaN|Infinity/);
      expect(document.getElementById('growth-table').querySelectorAll('.mini-row')).toHaveLength(4);
      expect(
        document.getElementById('growth-table').querySelectorAll('.mini-row-active'),
      ).toHaveLength(0);
    });

    it('highlights nothing when growthUsed matches no source', () => {
      renderGrowthTable(growth, 99);
      expect(
        document.getElementById('growth-table').querySelectorAll('.mini-row-active'),
      ).toHaveLength(0);
    });
  });

  describe('renderMultiplesTable', () => {
    function multiplesData(overrides = {}) {
      return {
        ticker: 'AAPL',
        currentPrice: 100,
        currency: 'USD',
        epsTtm: 5,
        asOf: '2026-08-22',
        historicalPe: { avg1y: 20, avg3y: 22, avg5y: 25 },
        growth: { epsTtmGrowthPercent: null },
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

    it('shows the EPS (TTM) row itself as effectiveEps, not the raw epsTtm, when they differ', () => {
      // Regression: this row previously always read data.epsTtm directly, even though Trailing
      // P/E two rows below it already used effectiveEps -- when a Yahoo-fallback effectiveEps
      // (e.g. resolveEpsWithFallback superseding a stale Twelve Data epsTtm) differed from
      // data.epsTtm, the panel showed two different EPS figures side by side.
      renderMultiplesTable(multiplesData({ epsTtm: 3.08 }), 10, 3.31, null);
      const text = document.getElementById('multiples-table').textContent;
      expect(text).toContain('3.31');
      expect(text).not.toContain('3.08');
    });

    it('shows EPS TTM growth (YoY) as n/a when epsTtmGrowthPercent is null', () => {
      // The realistic case today: this plan tier's income_statement caps at 6 quarters, one
      // short of the 8 calculateTtmEpsGrowthPercent needs, so it's null in practice.
      renderMultiplesTable(multiplesData({ growth: { epsTtmGrowthPercent: null } }), 10, 5, null);
      const text = document.getElementById('multiples-table').textContent;
      expect(text).toContain('EPS TTM growth');
      expect(text).toMatch(/n\/a/);
    });

    it('shows a real EPS TTM growth (YoY) percentage when available', () => {
      renderMultiplesTable(multiplesData({ growth: { epsTtmGrowthPercent: 68.57 } }), 10, 5, null);
      const text = document.getElementById('multiples-table').textContent;
      expect(text).toContain('68.57%');
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
        historical1yPercent: 10,
        historical3yPercent: null,
        historical5yPercent: 8,
        analystEstimate5yPercent: null,
      });
      const chips = document.getElementById('growth-chips').querySelectorAll('.chip');
      expect(chips).toHaveLength(2);
      expect(chips[0].textContent).toBe('1Y: 10.00%');
      expect(chips[1].textContent).toBe('5Y hist: 8.00%');
    });

    it('writes the chip value into the growth input when clicked', () => {
      document.getElementById('growth-input').value = '';
      renderGrowthChips({
        historical1yPercent: 12.345,
        historical3yPercent: null,
        historical5yPercent: null,
        analystEstimate5yPercent: null,
      });
      document.getElementById('growth-chips').querySelector('.chip').click();
      expect(document.getElementById('growth-input').value).toBe('12.35');
    });

    it('renders a chip for a real 0 rather than skipping it', () => {
      renderGrowthChips({
        historical1yPercent: 0,
        historical3yPercent: null,
        historical5yPercent: null,
        analystEstimate5yPercent: null,
      });
      const chips = document.getElementById('growth-chips').querySelectorAll('.chip');
      expect(chips).toHaveLength(1);
      expect(chips[0].textContent).toBe('1Y: 0.00%');
    });
  });

  describe('renderScenarioColumn / renderMethodCard', () => {
    const okResult = {
      ok: true,
      fairValue: 150,
      inputs: { epsTtm: 6, growthRatePercentRaw: 40, growthRatePercentClamped: 25 },
    };

    it('shows the fair value and an Undervalued verdict when above the price', () => {
      renderScenarioColumn('rule-one', 'base', okResult, 100);
      expect(document.getElementById('rule-one-base-fv').textContent).toBe('150.00');
      expect(document.getElementById('rule-one-base-verdict').textContent).toBe('Undervalued');
      expect(document.getElementById('rule-one-base-verdict').className).toContain('good');
    });

    it('shows Overvalued when the fair value is below the price', () => {
      renderScenarioColumn('rule-one', 'base', okResult, 200);
      expect(document.getElementById('rule-one-base-verdict').textContent).toBe('Overvalued');
      expect(document.getElementById('rule-one-base-verdict').className).toContain('bad');
    });

    it('surfaces the error code and clears inputs on a failed scenario', () => {
      renderScenarioColumn('rule-one', 'bear', { ok: false, error: 'MISSING_GROWTH_RATE' }, 100);
      expect(document.getElementById('rule-one-bear-fv').textContent).toBe('n/a');
      expect(document.getElementById('rule-one-bear-verdict').textContent).toBe(
        'FAILED (MISSING_GROWTH_RATE)',
      );
      expect(document.getElementById('rule-one-bear-inputs').innerHTML).toBe('');
    });

    it('shows both raw and clamped growth when the clamp actually applied', () => {
      renderScenarioColumn('rule-one', 'base', okResult, 100);
      const html = document.getElementById('rule-one-base-inputs').innerHTML;
      expect(html).toContain('40.00%');
      expect(html).toContain('25.00%');
    });

    it('shows a single growth figure when no clamping occurred', () => {
      renderScenarioColumn(
        'rule-one',
        'base',
        {
          ok: true,
          fairValue: 120,
          inputs: { epsTtm: 6, growthRatePercentRaw: 20, growthRatePercentClamped: 20 },
        },
        100,
      );
      const html = document.getElementById('rule-one-base-inputs').innerHTML;
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
      renderMethodCard(
        'rule-one',
        { bear: okResult, base: okResult, bull: okResult },
        100,
        (name) => [['exit P/E', name === 'bear' ? '10' : '20']],
      );
      expect(document.getElementById('rule-one-bear-inputs').innerHTML).toContain('10');
      expect(document.getElementById('rule-one-bull-inputs').innerHTML).toContain('20');
    });
  });

  describe('fetchHistory', () => {
    it('requests the unfiltered endpoint when no filter is given', async () => {
      let calledUrl;
      global.fetch = (url) => {
        calledUrl = url;
        return Promise.resolve({ json: () => Promise.resolve({ ok: true, data: [] }) });
      };
      await fetchHistory('');
      expect(calledUrl).toBe('/api/history?evaluator=Aviv');
    });

    it('url-encodes a ticker filter', async () => {
      let calledUrl;
      global.fetch = (url) => {
        calledUrl = url;
        return Promise.resolve({ json: () => Promise.resolve({ ok: true, data: [] }) });
      };
      await fetchHistory('BRK B&');
      expect(calledUrl).toBe('/api/history?ticker=BRK%20B%26&evaluator=Aviv');
    });

    it('swallows a rejected fetch without throwing', async () => {
      global.fetch = () => Promise.reject(new Error('network down'));
      await expect(fetchHistory('')).resolves.toBeUndefined();
    });

    it('ignores a stale response when a newer history fetch has since started', async () => {
      // Same race class as handleSubmit's concurrent-requests test above, but for the history
      // ticker filter: nothing sequenced fetchHistory's responses, so an earlier (slow) filter
      // request landing after a later (fast) one used to repaint the table with stale rows.
      let resolveFirst;
      const firstBody = new Promise((resolve) => {
        resolveFirst = resolve;
      });
      let call = 0;
      global.fetch = () => {
        call += 1;
        return call === 1
          ? Promise.resolve({ json: () => firstBody })
          : Promise.resolve({
              json: () =>
                Promise.resolve({
                  ok: true,
                  data: [
                    { id: 'new', ticker: 'MSFT', currentPrice: 400, currency: 'USD', years: 10 },
                  ],
                }),
            });
      };

      const slow = fetchHistory('G');
      await fetchHistory('MSFT');

      expect(document.getElementById('history-tbody').textContent).toContain('MSFT');

      resolveFirst({
        ok: true,
        data: [{ id: 'old', ticker: 'GOOGL', currentPrice: 170, currency: 'USD', years: 10 }],
      });
      await slow;

      // The stale GOOGL response must not have overwritten MSFT's row.
      expect(document.getElementById('history-tbody').textContent).not.toContain('GOOGL');
      expect(document.getElementById('history-tbody').textContent).toContain('MSFT');
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
      global.fetch = () => {
        called = true;
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ ok: true }) });
      };
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
      global.fetch = () =>
        Promise.resolve({
          ok: false,
          json: () => Promise.resolve({ ok: false, error: { message: 'disk full' } }),
        });

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
      const labels = Array.from(historyTbodyEl.querySelectorAll('.badge-scenario')).map(
        (el) => el.textContent,
      );
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
      const ruleOneCells = Array.from(rows).map(
        (r) => r.querySelectorAll('.table-val')[0].textContent,
      );
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

  describe('renderVerdict', () => {
    it('shows FAIR VALUE when diff is within 10%', () => {
      const el = document.createElement('div');
      renderVerdict(el, 102, 100);
      expect(el.textContent).toBe('FAIR VALUE');
      expect(el.className).toContain('neutral');
    });

    it('shows Undervalued when fair value is > 10% above price', () => {
      const el = document.createElement('div');
      renderVerdict(el, 111, 100);
      expect(el.textContent).toBe('Undervalued');
      expect(el.className).toContain('good');
    });

    it('shows Overvalued when fair value is > 10% below price', () => {
      const el = document.createElement('div');
      renderVerdict(el, 89, 100);
      expect(el.textContent).toBe('Overvalued');
      expect(el.className).toContain('bad');
    });

    it('returns n/a for currentPrice 0', () => {
      const el = document.createElement('div');
      renderVerdict(el, 100, 0);
      expect(el.textContent).toBe('n/a');
    });
  });

  describe('renderScenarioColumn', () => {
    it('appends percentage diff to verdict for valid prices', () => {
      document.body.innerHTML = `
        <div id="test-base-fv"></div>
        <div id="test-base-verdict"></div>
        <div id="test-base-inputs"></div>
      `;
      renderScenarioColumn('test', 'base', { ok: true, fairValue: 150, inputs: {} }, 100);
      const verdictEl = document.getElementById('test-base-verdict');
      const diffEl = verdictEl.nextSibling;
      expect(diffEl.className).toBe('scenario-diff');
      expect(diffEl.textContent).toContain('+50.00%');
    });

    it('does not append percentage diff if currentPrice is 0 (avoids Infinity)', () => {
      document.body.innerHTML = `
        <div id="test-base-fv"></div>
        <div id="test-base-verdict"></div>
        <div id="test-base-inputs"></div>
      `;
      renderScenarioColumn('test', 'base', { ok: true, fairValue: 150, inputs: {} }, 0);
      const verdictEl = document.getElementById('test-base-verdict');
      const diffEl = verdictEl.nextSibling;
      if (diffEl) {
        expect(diffEl.className).not.toBe('scenario-diff');
      }
    });
  });
});
