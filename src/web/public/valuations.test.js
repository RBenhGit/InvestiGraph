/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, beforeAll, beforeEach } from 'vitest';
import fs from 'fs';
import path from 'path';

// valuations.js is a plain <script> (no module system), same as app.js -- load it through a
// Function wrapper that hands back its top-level declarations, exactly the way app.test.js
// does. Before this file existed the entire "All Valuations" dashboard (table render, sort
// comparator, evaluator filter, upside chart) had zero coverage.
describe('valuations.js frontend', () => {
  let fmt;
  let parsePct;
  let renderTable;
  let renderChart;
  let populateEvaluatorFilter;
  let setValuations;
  let setSort;
  let chartConfigs;
  let tbodyEl;
  let filterInputEl;
  let evaluatorFilterEl;

  beforeAll(() => {
    document.body.innerHTML = `
      <input id="filter-input" />
      <select id="evaluator-filter"></select>
      <canvas id="upsideChart"></canvas>
      <table id="valuations-table">
        <thead>
          <tr>
            <th data-sort="date"></th>
            <th data-sort="ticker"></th>
            <th data-sort="price"></th>
            <th data-sort="lynch"></th>
            <th data-sort="lynch-pct"></th>
            <th data-sort="rule1"></th>
            <th data-sort="rule1-pct"></th>
            <th data-sort="evaluator"></th>
          </tr>
        </thead>
        <tbody id="valuations-tbody"></tbody>
      </table>
    `;

    chartConfigs = [];
    // Chart.js arrives from a CDN <script> in valuations.html, so it is a bare global here.
    global.Chart = class {
      constructor(ctx, config) {
        chartConfigs.push(config);
      }
      destroy() {}
    };
    // The script calls fetchValuations() at load time.
    global.fetch = () =>
      Promise.resolve({ json: () => Promise.resolve({ ok: true, data: [] }) });

    const code = fs.readFileSync(path.resolve(__dirname, 'valuations.js'), 'utf8');
    const run = new Function(
      'window',
      'document',
      `${code}
      return {
        fmt, parsePct, renderTable, renderChart, populateEvaluatorFilter,
        setValuations: (v) => { allValuations = v; },
        setSort: (col, asc) => { sortCol = col; sortAsc = asc; },
      };`,
    );
    const exports = run(window, document);
    fmt = exports.fmt;
    parsePct = exports.parsePct;
    renderTable = exports.renderTable;
    renderChart = exports.renderChart;
    populateEvaluatorFilter = exports.populateEvaluatorFilter;
    setValuations = exports.setValuations;
    setSort = exports.setSort;
    tbodyEl = document.getElementById('valuations-tbody');
    filterInputEl = document.getElementById('filter-input');
    evaluatorFilterEl = document.getElementById('evaluator-filter');
  });

  beforeEach(() => {
    filterInputEl.value = '';
    evaluatorFilterEl.innerHTML = '';
    evaluatorFilterEl.value = '';
    setSort('ticker', true);
    setValuations([]);
    chartConfigs.length = 0;
  });

  // A record in the modern nested shape written by the web UI's 3-scenario save.
  function scenarioRecord(overrides = {}) {
    return {
      id: overrides.id ?? 'id-1',
      ticker: overrides.ticker ?? 'AAPL',
      evaluatedAt: overrides.evaluatedAt ?? '2026-06-01T00:00:00.000Z',
      currentPrice: overrides.currentPrice ?? 100,
      currency: 'USD',
      evaluator: overrides.evaluator,
      base: {
        // `in` rather than `??` so a test can pass an explicit null and have it stay null.
        lynchFairValue: 'lynchFairValue' in overrides ? overrides.lynchFairValue : 120,
        ruleOneFairValue: 'ruleOneFairValue' in overrides ? overrides.ruleOneFairValue : 80,
      },
    };
  }

  // A record saved by the CLI (or by the app before scenarios existed): flat, no `base`.
  function legacyRecord(overrides = {}) {
    return {
      id: overrides.id ?? 'legacy-1',
      ticker: overrides.ticker ?? 'MSFT',
      evaluatedAt: overrides.evaluatedAt ?? '2026-05-01T00:00:00.000Z',
      currentPrice: overrides.currentPrice ?? 200,
      currency: 'USD',
      evaluator: overrides.evaluator,
      lynchFairValue: overrides.lynchFairValue ?? 250,
      ruleOneFairValue: overrides.ruleOneFairValue ?? 150,
    };
  }

  function rowTexts() {
    return [...tbodyEl.querySelectorAll('tr')].map((tr) =>
      [...tr.querySelectorAll('td')].map((td) => td.textContent),
    );
  }

  describe('fmt', () => {
    it('formats a number to two decimals', () => {
      expect(fmt(12.3456)).toBe('12.35');
    });

    it('returns n/a for null, undefined, and NaN', () => {
      expect(fmt(null)).toBe('n/a');
      expect(fmt(undefined)).toBe('n/a');
      expect(fmt(NaN)).toBe('n/a');
    });

    it('formats a real 0 rather than treating it as missing', () => {
      expect(fmt(0)).toBe('0.00');
    });
  });

  describe('parsePct', () => {
    it('computes percentage difference against the current price', () => {
      expect(parsePct(120, 100)).toBeCloseTo(20, 10);
      expect(parsePct(80, 100)).toBeCloseTo(-20, 10);
    });

    it('returns null when either side is missing', () => {
      expect(parsePct(null, 100)).toBeNull();
      expect(parsePct(undefined, 100)).toBeNull();
      expect(parsePct(120, null)).toBeNull();
      expect(parsePct(120, undefined)).toBeNull();
    });

    it('guards against a zero price instead of dividing by zero', () => {
      expect(parsePct(120, 0)).toBeNull();
    });
  });

  describe('renderTable — record shapes', () => {
    it('reads fair values out of `base` for a 3-scenario record', () => {
      setValuations([scenarioRecord()]);
      renderTable();
      const [row] = rowTexts();
      expect(row[1]).toBe('AAPL');
      expect(row[3]).toBe('120.00'); // Lynch base FV
      expect(row[5]).toBe('80.00'); // Rule #1 base FV
    });

    it('falls back to the flat record itself for a legacy record with no `base`', () => {
      setValuations([legacyRecord()]);
      renderTable();
      const [row] = rowTexts();
      expect(row[1]).toBe('MSFT');
      expect(row[3]).toBe('250.00');
      expect(row[5]).toBe('150.00');
    });

    it('renders a positive diff as +% and a negative diff as -%', () => {
      setValuations([scenarioRecord()]);
      renderTable();
      const [row] = rowTexts();
      expect(row[4]).toBe('+20.00%'); // 120 vs 100
      expect(row[6]).toBe('-20.00%'); // 80 vs 100
    });

    it('shows n/a for a diff when the price is zero rather than crashing or showing Infinity', () => {
      setValuations([scenarioRecord({ currentPrice: 0 })]);
      renderTable();
      const [row] = rowTexts();
      expect(row[4]).toBe('n/a');
      expect(row[6]).toBe('n/a');
    });

    it('defaults a record with no evaluator to Aviv', () => {
      setValuations([scenarioRecord()]);
      renderTable();
      expect(rowTexts()[0][7]).toBe('Aviv');
    });

    it('shows an invalid evaluatedAt as N/A instead of "Invalid Date"', () => {
      setValuations([scenarioRecord({ evaluatedAt: 'not-a-date' })]);
      renderTable();
      expect(rowTexts()[0][0]).toBe('N/A');
    });
  });

  describe('renderTable — filtering', () => {
    it('filters by ticker substring, case-insensitively', () => {
      setValuations([scenarioRecord(), legacyRecord()]);
      filterInputEl.value = 'msf';
      renderTable();
      expect(rowTexts().map((r) => r[1])).toEqual(['MSFT']);
    });

    it('filters by evaluator', () => {
      setValuations([
        scenarioRecord({ id: 'a', ticker: 'AAPL', evaluator: 'Ran' }),
        scenarioRecord({ id: 'b', ticker: 'NVDA', evaluator: 'Aviv' }),
      ]);
      evaluatorFilterEl.innerHTML =
        '<option value=""></option><option value="ran">Ran</option>';
      evaluatorFilterEl.value = 'ran';
      renderTable();
      expect(rowTexts().map((r) => r[1])).toEqual(['AAPL']);
    });

    it('an empty evaluator filter shows every evaluator', () => {
      setValuations([
        scenarioRecord({ id: 'a', ticker: 'AAPL', evaluator: 'Ran' }),
        scenarioRecord({ id: 'b', ticker: 'NVDA', evaluator: 'Aviv' }),
      ]);
      renderTable();
      expect(rowTexts()).toHaveLength(2);
    });
  });

  describe('renderTable — sorting', () => {
    it('sorts by ticker ascending and descending', () => {
      setValuations([
        scenarioRecord({ id: 'a', ticker: 'NVDA' }),
        scenarioRecord({ id: 'b', ticker: 'AAPL' }),
      ]);
      setSort('ticker', true);
      renderTable();
      expect(rowTexts().map((r) => r[1])).toEqual(['AAPL', 'NVDA']);

      setSort('ticker', false);
      renderTable();
      expect(rowTexts().map((r) => r[1])).toEqual(['NVDA', 'AAPL']);
    });

    it('sorts numerically by Rule #1 fair value, reading through the base shape', () => {
      setValuations([
        scenarioRecord({ id: 'a', ticker: 'AAA', ruleOneFairValue: 10 }),
        scenarioRecord({ id: 'b', ticker: 'BBB', ruleOneFairValue: 90 }),
      ]);
      setSort('rule1', false);
      renderTable();
      expect(rowTexts().map((r) => r[1])).toEqual(['BBB', 'AAA']);
    });

    it('sorts by upside percentage, not by raw fair value', () => {
      // BBB has the higher fair value but the worse upside -- sorting on rule1-pct must not
      // just mirror the rule1 ordering.
      setValuations([
        scenarioRecord({ id: 'a', ticker: 'AAA', currentPrice: 10, ruleOneFairValue: 20 }), // +100%
        scenarioRecord({ id: 'b', ticker: 'BBB', currentPrice: 100, ruleOneFairValue: 110 }), // +10%
      ]);
      setSort('rule1-pct', false);
      renderTable();
      expect(rowTexts().map((r) => r[1])).toEqual(['AAA', 'BBB']);
    });

    it('sorts nulls to the bottom regardless of direction', () => {
      setValuations([
        scenarioRecord({ id: 'a', ticker: 'AAA', ruleOneFairValue: null }),
        scenarioRecord({ id: 'b', ticker: 'BBB', ruleOneFairValue: 50 }),
      ]);
      setSort('rule1', true);
      renderTable();
      expect(rowTexts().map((r) => r[1])).toEqual(['BBB', 'AAA']);

      setSort('rule1', false);
      renderTable();
      expect(rowTexts().map((r) => r[1])).toEqual(['BBB', 'AAA']);
    });

    it('sorts by date newest-first when descending', () => {
      setValuations([
        scenarioRecord({ id: 'a', ticker: 'OLD', evaluatedAt: '2026-01-01T00:00:00.000Z' }),
        scenarioRecord({ id: 'b', ticker: 'NEW', evaluatedAt: '2026-08-01T00:00:00.000Z' }),
      ]);
      setSort('date', false);
      renderTable();
      expect(rowTexts().map((r) => r[1])).toEqual(['NEW', 'OLD']);
    });
  });

  describe('populateEvaluatorFilter', () => {
    it('lists each distinct evaluator once, plus an All option', () => {
      setValuations([
        scenarioRecord({ id: 'a', evaluator: 'Ran' }),
        scenarioRecord({ id: 'b', evaluator: 'Aviv' }),
        scenarioRecord({ id: 'c', evaluator: 'Ran' }),
      ]);
      populateEvaluatorFilter();
      const options = [...evaluatorFilterEl.querySelectorAll('option')].map((o) => o.textContent);
      expect(options).toEqual(['All Evaluators', 'Aviv', 'Ran']);
    });

    it('buckets records with no evaluator under the Aviv default', () => {
      setValuations([scenarioRecord({ id: 'a' })]);
      populateEvaluatorFilter();
      const options = [...evaluatorFilterEl.querySelectorAll('option')].map((o) => o.textContent);
      expect(options).toEqual(['All Evaluators', 'Aviv']);
    });
  });

  describe('renderChart', () => {
    function recent(overrides = {}) {
      const d = new Date();
      d.setMonth(d.getMonth() - 1);
      return scenarioRecord({ evaluatedAt: d.toISOString(), ...overrides });
    }

    it('plots one bar per record, sorted by upside descending', () => {
      setValuations([
        recent({ id: 'a', ticker: 'LOW', currentPrice: 100, ruleOneFairValue: 110 }), // +10%
        recent({ id: 'b', ticker: 'HIGH', currentPrice: 100, ruleOneFairValue: 200 }), // +100%
      ]);
      renderChart();
      const cfg = chartConfigs.at(-1);
      expect(cfg.data.labels).toEqual(['HIGH', 'LOW']);
      expect(cfg.data.datasets[0].data[0]).toBeCloseTo(100, 10);
    });

    it('excludes records older than six months', () => {
      const old = new Date();
      old.setMonth(old.getMonth() - 12);
      setValuations([
        recent({ id: 'a', ticker: 'FRESH' }),
        scenarioRecord({ id: 'b', ticker: 'STALE', evaluatedAt: old.toISOString() }),
      ]);
      renderChart();
      expect(chartConfigs.at(-1).data.labels).toEqual(['FRESH']);
    });

    it('qualifies a repeated ticker with the evaluator name so two evaluators are distinguishable', () => {
      // /api/valuations returns one row per (ticker, evaluator) pair, so this is the normal
      // shape as soon as two people value the same company -- bare labels made the bars
      // indistinguishable.
      setValuations([
        recent({ id: 'a', ticker: 'AAPL', evaluator: 'Ran', currentPrice: 100, ruleOneFairValue: 200 }),
        recent({ id: 'b', ticker: 'AAPL', evaluator: 'Aviv', currentPrice: 100, ruleOneFairValue: 110 }),
      ]);
      renderChart();
      expect(chartConfigs.at(-1).data.labels).toEqual(['AAPL (Ran)', 'AAPL (Aviv)']);
    });

    it('leaves a non-repeated ticker as a bare label', () => {
      setValuations([
        recent({ id: 'a', ticker: 'AAPL', evaluator: 'Ran' }),
        recent({ id: 'b', ticker: 'NVDA', evaluator: 'Aviv' }),
      ]);
      const labels = (renderChart(), chartConfigs.at(-1).data.labels);
      expect(labels).toContain('AAPL');
      expect(labels).toContain('NVDA');
    });

    it('treats an unusable upside as 0 rather than dropping the bar', () => {
      setValuations([recent({ id: 'a', ticker: 'ZERO', currentPrice: 0 })]);
      renderChart();
      expect(chartConfigs.at(-1).data.datasets[0].data).toEqual([0]);
    });

    it('colors negative upside differently from positive', () => {
      setValuations([
        recent({ id: 'a', ticker: 'UP', currentPrice: 100, ruleOneFairValue: 150 }),
        recent({ id: 'b', ticker: 'DOWN', currentPrice: 100, ruleOneFairValue: 50 }),
      ]);
      renderChart();
      const colors = chartConfigs.at(-1).data.datasets[0].backgroundColor;
      expect(colors[0]).not.toBe(colors[1]);
    });
  });
});
