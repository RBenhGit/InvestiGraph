// Plain script, no bundler/framework. Talks to POST /api/valuate only -- no valuation math here,
// that would reimplement the formulas the same way the base design doc forbids in the CLI.

const tickerInput = document.getElementById('ticker-input');
const epsInput = document.getElementById('eps-input');
const goBtn = document.getElementById('go-btn');
const refreshBtn = document.getElementById('refresh-btn');
const growthInput = document.getElementById('growth-input');
const exitPeInput = document.getElementById('exit-pe-input');
const requiredReturnInput = document.getElementById('required-return-input');
const yearsInput = document.getElementById('years-input');
const mosSelect = document.getElementById('mos-select');
const bearGrowthInput = document.getElementById('bear-growth-input');
const bearExitPeInput = document.getElementById('bear-exit-pe-input');
const bearRequiredReturnInput = document.getElementById('bear-required-return-input');
const bullGrowthInput = document.getElementById('bull-growth-input');
const bullExitPeInput = document.getElementById('bull-exit-pe-input');
const bullRequiredReturnInput = document.getElementById('bull-required-return-input');
const notesInput = document.getElementById('notes-input');
const growthChips = document.getElementById('growth-chips');
const errorCard = document.getElementById('error-card');
const result = document.getElementById('result');
const cards = document.getElementById('cards');
const priceValueEl = document.getElementById('price-value');
const priceMetaEl = document.getElementById('price-meta');
const priceDeltasEl = document.getElementById('price-deltas');
const growthTableEl = document.getElementById('growth-table');
const multiplesTableEl = document.getElementById('multiples-table');
const analystTableEl = document.getElementById('analyst-table');

// History elements
const evaluatorSelect = document.getElementById('evaluator-select');
const addEvaluatorBtn = document.getElementById('add-evaluator-btn');
const delEvaluatorBtn = document.getElementById('del-evaluator-btn');
const saveBtn = document.getElementById('save-btn');
const saveStatus = document.getElementById('save-status');
const historyEmpty = document.getElementById('history-empty');
const historyTableContainer = document.getElementById('history-table-container');
const historyTbody = document.getElementById('history-tbody');
const historyFilter = document.getElementById('history-filter');
const historyRefreshBtn = document.getElementById('history-refresh-btn');

let currentValuation = null;

// המרחק המקסימלי (באחוזים) מהמחיר הנוכחי שעדיין נחשב "הוגן", לא Undervalued/Overvalued.
const FAIR_VALUE_TOLERANCE_PERCENT = 5;

// Monotonic id for /api/valuate requests. The Go button is disabled while one is in flight,
// but "Refresh Live" is not, and responses can arrive out of order -- so without this the LAST
// response to land wins the DOM even when it belongs to an EARLIER request, painting one
// ticker's banner next to another ticker's fair values. Every response checks that it is still
// the newest before touching anything.
let latestValuateRequestId = 0;

// Same race, different endpoint: fetchHistory is called on every keystroke in the history
// ticker filter (plus on save/delete/refresh), and nothing sequenced those responses either --
// an earlier filter request resolving after a later one repaints the table with stale, wrong-
// filter rows.
let latestHistoryRequestId = 0;

/** Mirrors cli/index.ts's formatStockDataError, for display purposes only. */
function formatStockDataError(error) {
  switch (error.type) {
    case 'NOT_FOUND':
      return `Ticker "${error.ticker}" not found.`;
    case 'INSUFFICIENT_DATA':
      return `Insufficient data for "${error.ticker}": ${error.reason}`;
    case 'EMPTY_RESPONSE':
      return `Empty response from "${error.endpoint}" for "${error.ticker}".`;
    case 'API_ERROR':
      return `API error from "${error.endpoint}" for "${error.ticker}": ${error.message}`;
    case 'RATE_LIMIT':
      return `Rate limit exceeded from "${error.endpoint}" for "${error.ticker}". Please wait a minute and try again.`;
    case 'INVALID_CURRENCY_UNIT':
      return `Invalid currency unit for "${error.ticker}": ${error.detail}`;
    default:
      return 'Unknown error.';
  }
}

function fmt(value) {
  return value === null || value === undefined ? 'n/a' : Number(value).toFixed(2);
}

function fmtPercent(value) {
  return value === null || value === undefined ? 'n/a' : `${Number(value).toFixed(2)}%`;
}

/** A usable divisor for a percentage delta: not null/undefined/NaN, and strictly positive.
 * parseNumber treats a real 0 as a value (not missing) and fetchStockData only rejects null, so
 * a "0.00" close price can reach here and would render Infinity as "+Infinity%" if divided into.
 * Shared by renderPriceDelta and priceTargetValue -- both hit the exact same zero-price bug. */
function isValidPrice(price) {
  return price !== null && price !== undefined && !Number.isNaN(price) && price > 0;
}

function formatDate(isoString) {
  if (!isoString) return 'n/a';
  try {
    const d = new Date(isoString);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  } catch {
    return isoString;
  }
}

function setLoading(isLoading) {
  if (goBtn) goBtn.disabled = isLoading;
  // Refresh Live triggers the same request as Go, so it has to be disabled alongside it --
  // leaving it live is what let two lookups overlap in the first place. The requestId guard in
  // handleSubmit still backstops any race this doesn't prevent (e.g. Enter in the ticker field).
  if (refreshBtn) refreshBtn.disabled = isLoading;
  if (result) result.style.opacity = isLoading ? '0.5' : '1';
}

function showError(message) {
  if (result) result.hidden = true;
  if (errorCard) {
    errorCard.hidden = false;
    errorCard.textContent = message;
  }
}

function clearError() {
  if (errorCard) errorCard.hidden = true;
}

/** Current price vs. one fair-value estimate: upside/downside % and a verdict pill. */
function renderPriceDelta(label, fairValue, currentPrice, dotColorVar) {
  const div = document.createElement('div');
  div.className = 'price-delta';

  const labelDiv = document.createElement('div');
  labelDiv.className = 'price-delta-label';
  labelDiv.innerHTML = `<span class="dot" style="background: var(${dotColorVar})"></span>${label}`;

  const valueDiv = document.createElement('div');
  valueDiv.className = 'price-delta-value';

  if (
    fairValue === null ||
    fairValue === undefined ||
    Number.isNaN(fairValue) ||
    !isValidPrice(currentPrice)
  ) {
    valueDiv.textContent = 'n/a';
  } else {
    const diffPercent = (fairValue / currentPrice - 1) * 100;
    const undervalued = diffPercent > 0;
    valueDiv.innerHTML = `<b>${fmt(fairValue)}</b> <span class="${undervalued ? 'good' : 'bad'}">${undervalued ? '+' : ''}${fmt(diffPercent)}%</span>`;
  }

  div.append(labelDiv, valueDiv);
  return div;
}

/**
 * `effectiveEps`/`epsSource`/`epsSourceDetail` come from the server's resolveEpsWithFallback
 * (see src/data/resolveEps.ts) -- when Twelve Data's epsTtm looked stale (data.staleTtmWarning)
 * and Yahoo's independent trailingEps was available, effectiveEps reflects Yahoo's figure
 * instead, and epsSource says which one actually won so the banner never silently shows a
 * Yahoo-sourced number as if it were Twelve Data's.
 */
function renderPriceBanner(data, lynch, ruleOne, effectiveEps, epsSource, epsSourceDetail) {
  if (!priceValueEl || !priceMetaEl || !priceDeltasEl) return;
  priceValueEl.textContent = `${fmt(data.currentPrice)} ${data.currency}`;
  const epsToShow = typeof effectiveEps === 'number' ? effectiveEps : data.epsTtm;

  let note = '';
  if (epsSource === 'yahoo-fallback') {
    note = ` · ⓘ EPS from Yahoo Finance (Twelve Data's figure looked stale — see tooltip)`;
  } else if (epsSource === 'twelvedata-stale-no-fallback') {
    note =
      ' · ⚠ EPS (TTM) may be stale (diverges from provider trailing P/E) — Yahoo Finance fallback was unavailable';
  } else if (data.staleTtmWarning) {
    note = ' · ⚠ EPS (TTM) may be stale (diverges from provider trailing P/E — check for a recent earnings release)';
  }
  priceMetaEl.textContent = `${data.ticker} · EPS (TTM) ${fmt(epsToShow)} · as of ${data.asOf}${note}`;
  priceMetaEl.title = epsSourceDetail || '';
  const isWarning = epsSource === 'twelvedata-stale-no-fallback' || (!epsSource && data.staleTtmWarning);
  priceMetaEl.classList.toggle('stale-warning', isWarning);
  priceMetaEl.classList.toggle('eps-fallback-note', epsSource === 'yahoo-fallback');

  priceDeltasEl.innerHTML = '';
  priceDeltasEl.append(
    renderPriceDelta(
      'Peter Lynch fair value',
      lynch.ok ? lynch.fairValue : null,
      data.currentPrice,
      '--accent-a',
    ),
    renderPriceDelta(
      'Rule #1 fair value',
      ruleOne.ok ? ruleOne.fairValue : null,
      data.currentPrice,
      '--accent-b',
    ),
  );
}

/**
 * Small label/value row for the growth-sources and multiples panels.
 *
 * `value` is rendered as TEXT by default. It used to be assigned straight to `innerHTML`, but
 * some values are strings that arrive from a third-party API (`recommendationKey` from Yahoo),
 * so markup in them was parsed into live DOM instead of being displayed -- a `<img src=x
 * onerror=...>` in that field really did become an element with a working handler. Callers that
 * genuinely need markup (the locally-built `health-badge` spans, whose only interpolated parts
 * are numbers through `fmt()`) must opt in explicitly with `{ html: true }`.
 */
function tableRow(label, value, opts) {
  const row = document.createElement('div');
  row.className = 'mini-row';
  const labelDiv = document.createElement('div');
  labelDiv.className = 'mini-label';
  labelDiv.textContent = label;
  const valueDiv = document.createElement('div');
  valueDiv.className = 'mini-value';
  if (opts && opts.html) {
    valueDiv.innerHTML = value;
  } else {
    valueDiv.textContent = value;
  }
  row.append(labelDiv, valueDiv);
  if (opts && opts.highlight) row.classList.add('mini-row-active');
  if (opts && opts.barFill !== undefined) {
    row.classList.add('mini-row-bar');
    row.style.setProperty('--bar-fill', String(opts.barFill));
  }
  return row;
}

/** Every EPS growth-rate source side by side, with the one currently in use highlighted */
function renderGrowthTable(growth, growthUsed) {
  if (!growthTableEl) return;
  growthTableEl.innerHTML = '';
  const sources = [
    { key: 'historical1yPercent', label: 'Historical, 1Y' },
    { key: 'historical3yPercent', label: 'Historical, 3Y CAGR' },
    { key: 'historical5yPercent', label: 'Historical, 5Y' },
    { key: 'analystEstimate5yPercent', label: 'Analyst estimate, 5Y' },
  ];
  const magnitudes = sources
    .map((source) => growth[source.key])
    .filter((value) => value !== null && value !== undefined)
    .map(Math.abs);
  const maxMagnitude = magnitudes.length > 0 ? Math.max(...magnitudes) : 0;

  for (const source of sources) {
    const value = growth[source.key];
    const isActive = value !== null && value !== undefined && value === growthUsed;
    const barFill =
      value !== null && value !== undefined && maxMagnitude > 0
        ? Math.abs(value) / maxMagnitude
        : 0;
    growthTableEl.append(
      tableRow(source.label, fmtPercent(value), { highlight: isActive, barFill }),
    );
  }
}

/** Historical average P/E plus trailing P/E and PEG */
function renderMultiplesTable(data, effectiveGrowth, effectiveEps, analystConsensus) {
  if (!multiplesTableEl) return;
  multiplesTableEl.innerHTML = '';

  // Calculate trailing P/E dynamically based on the effective EPS
  const currentPrice = data.currentPrice;
  const epsToUse = effectiveEps && effectiveEps > 0 ? effectiveEps : data.epsTtm;
  const trailingPe = epsToUse && epsToUse > 0 ? currentPrice / epsToUse : null;

  // Calculate local PEG instead of relying on provider's unreliable metric
  let pegRatio = null;
  if (trailingPe !== null && effectiveGrowth !== null && effectiveGrowth > 0) {
    pegRatio = trailingPe / effectiveGrowth;
  }

  let pegFormatted = fmt(pegRatio);
  if (pegRatio !== null) {
    const pegClass = pegRatio <= 1.0 ? 'good' : pegRatio <= 1.5 ? 'warning' : 'bad';
    pegFormatted = `<span class="health-badge ${pegClass}">${fmt(pegRatio)}</span>`;
  }

  multiplesTableEl.append(
    // epsToUse (not data.epsTtm) so this matches the price banner and Trailing P/E right below
    // it -- previously showed Twelve Data's raw (possibly Yahoo-superseded) figure here while
    // Trailing P/E, computed two lines above from the same epsToUse, already reflected the
    // resolved value, producing an internally-inconsistent panel.
    tableRow('EPS (TTM)', fmt(epsToUse)),
    // Rolling 12-month-vs-12-month-ago growth -- distinct from the calendar-year CAGR figures in
    // the growth-sources panel above (never a candidate in that fallback chain, so it doesn't
    // belong there) and never fed into either valuation method. Needs 8 consecutive quarters,
    // which this plan tier's income_statement cap (6) can't supply -- "n/a" here is honest, not
    // a bug; see calculateTtmEpsGrowthPercent in src/data/twelvedata/normalize.ts.
    tableRow('EPS TTM growth (YoY)', fmtPercent(data.growth.epsTtmGrowthPercent)),
    tableRow('Median P/E, 1Y', fmt(data.historicalPe.avg1y)),
    tableRow('Median P/E, 3Y', fmt(data.historicalPe.avg3y)),
    tableRow('Median P/E, 5Y', fmt(data.historicalPe.avg5y)),
    tableRow('Trailing P/E (current)', fmt(trailingPe)),
    tableRow('PEG ratio (local)', pegFormatted, { html: true }),
  );

  // priceToSales is typed `number | null` and is never `undefined`, so a `!== undefined`
  // check is always true and rendered a permanent "P/S ratio (TTM): n/a" row for every
  // ticker Yahoo has no P/S coverage for. Same trap as the Financial Health header below.
  if (
    analystConsensus &&
    analystConsensus.priceToSales !== null &&
    analystConsensus.priceToSales !== undefined
  ) {
    multiplesTableEl.append(tableRow('P/S ratio (TTM)', fmt(analystConsensus.priceToSales)));
  }
}

/** Yahoo Finance analyst consensus */
function renderAnalystTable(analystConsensus, currentPrice) {
  if (!analystTableEl) return;
  analystTableEl.innerHTML = '';

  if (!analystConsensus) {
    analystTableEl.append(tableRow('Analyst data', 'unavailable'));
    return;
  }

  const { nextYearEpsGrowthPercent, priceTarget, recommendationKey, beta, ruleOf40 } =
    analystConsensus;

  const recommendationLabel = recommendationKey
    ? recommendationKey.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
    : 'n/a';

  analystTableEl.append(
    tableRow('Recommendation', recommendationLabel),
    tableRow('Next-year EPS growth (est.)', fmtPercent(nextYearEpsGrowthPercent)),
    tableRow('Price target, mean', priceTargetValue(priceTarget.mean, currentPrice)),
    tableRow('Price target, high', priceTargetValue(priceTarget.high, currentPrice)),
    tableRow('Price target, low', priceTargetValue(priceTarget.low, currentPrice)),
    tableRow('Number of analysts', priceTarget.numberOfAnalysts ?? 'n/a'),
  );

  // beta/ruleOf40 are typed `number | null` (never `undefined`) -- gate the section header on
  // `!== null` too, matching the row-level checks below, so the header isn't shown when both
  // values are genuinely missing (e.g. a ticker Yahoo has no summaryDetail/financialData
  // coverage for).
  if (beta !== null || ruleOf40 !== null) {
    const divider = document.createElement('tr');
    divider.innerHTML =
      '<td colspan="2" style="padding-top: 1rem; border-bottom: 1px solid var(--border); font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); font-weight: 600;">Financial Health</td>';
    analystTableEl.append(divider);

    if (ruleOf40 !== undefined && ruleOf40 !== null) {
      // >= 100 is tagged bad, not good -- a Rule of 40 that high is far more likely a data
      // artifact (e.g. a period mismatch between the growth and margin figures) than a real
      // score. Live-confirmed after the period-mismatch fix: NVDA/PLTR/ANET all land well above
      // 40 and below 100 once revenue growth and EBITDA margin are period-matched; a figure at
      // or above 100 (like the pre-fix IONQ case of 286.80, or NVDA's pre-fix 150.49) should
      // read as suspicious, not excellent.
      const healthClass =
        ruleOf40 >= 100 ? 'bad' : ruleOf40 >= 40 ? 'good' : ruleOf40 >= 20 ? 'warning' : 'bad';
      analystTableEl.append(
        tableRow(
          'Rule of 40',
          `<span class="health-badge ${healthClass}">${fmt(ruleOf40)}%</span>`,
          { html: true },
        ),
      );
    }
    if (beta !== undefined && beta !== null) {
      const betaClass = beta < 1.0 ? 'good' : beta < 1.5 ? 'warning' : 'bad';
      analystTableEl.append(
        tableRow(
          'Beta (Volatility)',
          `<span class="health-badge ${betaClass}">${fmt(beta)}</span>`,
          { html: true },
        ),
      );
    }
  }
}

function priceTargetValue(target, currentPrice) {
  if (target === null || target === undefined) return 'n/a';
  // Same zero-denominator guard as renderPriceDelta above -- a 0 currentPrice would render the
  // analyst price target's delta as "+Infinity%". Show the target without a delta instead.
  if (!isValidPrice(currentPrice)) {
    return fmt(target);
  }
  const diffPercent = (target / currentPrice - 1) * 100;
  const sign = diffPercent > 0 ? '+' : '';
  return `${fmt(target)} (${sign}${fmt(diffPercent)}%)`;
}

/** Growth-source chips */
function renderGrowthChips(growth) {
  if (!growthChips) return;
  growthChips.innerHTML = '';
  const sources = [
    { key: 'historical1yPercent', label: '1Y' },
    { key: 'historical3yPercent', label: '3Y' },
    { key: 'historical5yPercent', label: '5Y hist' },
    { key: 'analystEstimate5yPercent', label: 'Analyst 5Y' },
  ];
  for (const source of sources) {
    const value = growth[source.key];
    if (value === null || value === undefined) continue;
    const chip = document.createElement('button');
    chip.type = 'button';
    chip.className = 'chip';
    chip.textContent = `${source.label}: ${fmt(value)}%`;
    chip.addEventListener('click', () => {
      if (growthInput) {
        growthInput.value = Number(Number(value).toFixed(2));
      }
    });
    growthChips.append(chip);
  }
}

function renderVerdict(el, fairValue, currentPrice) {
  if (!isValidPrice(currentPrice) || fairValue === null || fairValue === undefined) {
    el.textContent = 'n/a';
    el.className = 'verdict';
    return;
  }
  const diffPercent = (fairValue / currentPrice - 1) * 100;
  if (Math.abs(diffPercent) <= FAIR_VALUE_TOLERANCE_PERCENT) {
    el.textContent = 'FAIR VALUE';
    el.className = 'verdict neutral';
  } else if (diffPercent > 0) {
    el.textContent = 'Undervalued';
    el.className = 'verdict good';
  } else {
    el.textContent = 'Overvalued';
    el.className = 'verdict bad';
  }
}

function growthIO(inputs) {
  const raw = inputs.growthRatePercentRaw;
  const clamped = inputs.growthRatePercentClamped;
  if (raw !== clamped) {
    return `<span class="io"><span class="raw">${fmt(raw)}%</span><b class="clamped">${fmt(clamped)}%</b></span>`;
  }
  return `<span class="io">growth: <b>${fmt(clamped)}%</b></span>`;
}

function renderScenarioColumn(prefix, scenario, result, currentPrice, extraFields) {
  const fairValueEl = document.getElementById(`${prefix}-${scenario}-fv`);
  const verdictEl = document.getElementById(`${prefix}-${scenario}-verdict`);
  const inputsEl = document.getElementById(`${prefix}-${scenario}-inputs`);

  if (!fairValueEl || !verdictEl || !inputsEl) return;

  if (!result.ok) {
    fairValueEl.textContent = 'n/a';
    verdictEl.textContent = `FAILED (${result.error})`;
    verdictEl.className = 'verdict bad';
    inputsEl.innerHTML = '';
    return;
  }

  fairValueEl.textContent = fmt(result.fairValue);
  renderVerdict(verdictEl, result.fairValue, currentPrice);

  if (isValidPrice(currentPrice) && result.fairValue !== null && result.fairValue !== undefined) {
    const diffPercent = (result.fairValue / currentPrice - 1) * 100;
    const sign = diffPercent > 0 ? '+' : '';
    const diffDiv = document.createElement('div');
    diffDiv.className = 'scenario-diff';
    diffDiv.style.fontSize = '0.8rem';
    diffDiv.style.fontFamily = 'ui-monospace, monospace';
    diffDiv.style.marginTop = '-0.8rem';
    diffDiv.style.marginBottom = '1.1rem';
    diffDiv.style.color = 'var(--ink-soft)';
    diffDiv.textContent = `Diff: ${sign}${fmt(diffPercent)}%`;
    // Insert diffDiv after verdictEl
    verdictEl.parentNode.insertBefore(diffDiv, verdictEl.nextSibling);
  }

  const extraHtml = (extraFields || [])
    .map(([label, value]) => `<span class="io">${label}: <b>${value}</b></span>`)
    .join('');
  inputsEl.innerHTML = growthIO(result.inputs) + extraHtml;
}

function renderMethodCard(prefix, results, currentPrice, getExtrasFn) {
  renderScenarioColumn(
    prefix,
    'bear',
    results.bear,
    currentPrice,
    getExtrasFn ? getExtrasFn('bear', results.bear) : undefined,
  );
  renderScenarioColumn(
    prefix,
    'base',
    results.base,
    currentPrice,
    getExtrasFn ? getExtrasFn('base', results.base) : undefined,
  );
  renderScenarioColumn(
    prefix,
    'bull',
    results.bull,
    currentPrice,
    getExtrasFn ? getExtrasFn('bull', results.bull) : undefined,
  );
}

// ---------------- History Functions ----------------

async function fetchHistory(filterTicker) {
  if (!historyTbody) return;
  const requestId = ++latestHistoryRequestId;
  try {
    const evaluatorParam = evaluatorSelect ? `evaluator=${encodeURIComponent(evaluatorSelect.value)}` : '';
    let url = '/api/history';
    const params = [];
    if (filterTicker && filterTicker.trim()) params.push(`ticker=${encodeURIComponent(filterTicker.trim())}`);
    if (evaluatorParam) params.push(evaluatorParam);
    if (params.length > 0) url += '?' + params.join('&');

    const response = await fetch(url);
    const body = await response.json();

    // A newer history fetch started while this one was in flight -- its result already owns
    // the table, so this stale response must not repaint it.
    if (requestId !== latestHistoryRequestId) return;

    if (!body || !body.ok) return;

    renderHistoryTable(body.data);
  } catch (err) {
    if (requestId !== latestHistoryRequestId) return;
    console.error('Failed to fetch history:', err);
  }
}

function renderHistoryTable(records) {
  if (!historyTbody || !historyEmpty || !historyTableContainer) return;

  if (!records || records.length === 0) {
    historyEmpty.hidden = false;
    historyTableContainer.hidden = true;
    historyTbody.innerHTML = '';
    return;
  }

  historyEmpty.hidden = true;
  historyTableContainer.hidden = false;
  historyTbody.innerHTML = '';

  for (const item of records) {
    // If it's a legacy record without 'base', wrap it to look like one.
    const scenarios = item.base
      ? [
          { name: 'Bear', data: item.bear || item.base },
          { name: 'Base', data: item.base },
          { name: 'Bull', data: item.bull || item.base },
        ]
      : [
          {
            name: 'Base',
            data: {
              growthRatePercent: item.growthRatePercent,
              exitPeMultiple: item.exitPeMultiple,
              requiredReturnPercent: item.requiredReturnPercent,
              mosPercent: item.mosPercent,
              lynchFairValue: item.lynchFairValue,
              ruleOneFairValue: item.ruleOneFairValue,
            },
          },
        ];

    for (let i = 0; i < scenarios.length; i++) {
      const scenario = scenarios[i];
      const isFirstRow = i === 0;
      const isBaseRow = scenario.name === 'Base';
      const rowSpan = scenarios.length;

      const tr = document.createElement('tr');
      if (scenarios.length > 1) {
        tr.classList.add(`history-row-${scenario.name.toLowerCase()}`);
      }

      // Date (only on first row)
      if (isFirstRow) {
        const tdDate = document.createElement('td');
        tdDate.className = 'table-date';
        tdDate.rowSpan = rowSpan;
        tdDate.textContent = formatDate(item.evaluatedAt);
        tr.append(tdDate);
      }

      // Ticker & Scenario Name
      const tdTicker = document.createElement('td');
      const badge = document.createElement('span');
      badge.className = 'badge-ticker';
      badge.textContent = item.ticker;
      if (scenarios.length > 1) {
        const scenarioLabel = document.createElement('span');
        scenarioLabel.className = `badge-scenario scenario-${scenario.name.toLowerCase()}`;
        scenarioLabel.textContent = scenario.name;
        tdTicker.append(badge, ' ', scenarioLabel);
      } else {
        tdTicker.append(badge);
      }
      tr.append(tdTicker);

      // Price (only on first row)
      if (isFirstRow) {
        const tdPrice = document.createElement('td');
        tdPrice.className = 'table-price';
        tdPrice.rowSpan = rowSpan;
        tdPrice.textContent = `${fmt(item.currentPrice)} ${item.currency || 'USD'}`;
        tr.append(tdPrice);
      }

      // Rule #1 Fair Value
      const tdRuleOne = document.createElement('td');
      tdRuleOne.className = 'table-val';
      if (scenario.data.ruleOneFairValue !== null && scenario.data.ruleOneFairValue !== undefined) {
        const diff = (scenario.data.ruleOneFairValue / item.currentPrice - 1) * 100;
        const isGood = diff > 0;
        tdRuleOne.innerHTML = `<b>${fmt(scenario.data.ruleOneFairValue)}</b> <span class="${isGood ? 'good' : 'bad'}">(${isGood ? '+' : ''}${fmt(diff)}%)</span>`;
      } else {
        tdRuleOne.textContent = 'n/a';
      }
      tr.append(tdRuleOne);

      // Lynch Fair Value
      const tdLynch = document.createElement('td');
      tdLynch.className = 'table-val';
      if (scenario.data.lynchFairValue !== null && scenario.data.lynchFairValue !== undefined) {
        const diff = (scenario.data.lynchFairValue / item.currentPrice - 1) * 100;
        const isGood = diff > 0;
        tdLynch.innerHTML = `<b>${fmt(scenario.data.lynchFairValue)}</b> <span class="${isGood ? 'good' : 'bad'}">(${isGood ? '+' : ''}${fmt(diff)}%)</span>`;
      } else {
        tdLynch.textContent = 'n/a';
      }
      tr.append(tdLynch);

      // Growth
      const tdGrowth = document.createElement('td');
      tdGrowth.className = 'table-val';
      tdGrowth.textContent = fmtPercent(scenario.data.growthRatePercent);
      tr.append(tdGrowth);

      // Assumptions
      const tdAssump = document.createElement('td');
      tdAssump.className = 'table-assumptions';
      const mosText = scenario.data.mosPercent ? ` | MoS: ${scenario.data.mosPercent}%` : '';
      const epsText = item.epsOverride
        ? ` | Adj.EPS: ${fmt(item.epsOverride)}`
        : item.epsTtm
          ? ` | EPS: ${fmt(item.epsTtm)}`
          : '';
      tdAssump.textContent = `PE: ${fmt(scenario.data.exitPeMultiple)} | Req: ${fmt(scenario.data.requiredReturnPercent)}% | ${item.years}y${mosText}${epsText}`;
      tr.append(tdAssump);

      // Notes (only on first row)
      if (isFirstRow) {
        const tdNotes = document.createElement('td');
        tdNotes.className = 'table-notes';
        tdNotes.rowSpan = rowSpan;
        tdNotes.textContent = item.notes || '—';
        if (item.notes) tdNotes.title = item.notes;
        tr.append(tdNotes);
      }

      // Actions (only on first row)
      if (isFirstRow) {
        const tdActions = document.createElement('td');
        tdActions.className = 'table-actions';
        tdActions.rowSpan = rowSpan;

        const loadBtn = document.createElement('button');
        loadBtn.type = 'button';
        loadBtn.className = 'btn-action-load';
        loadBtn.textContent = 'Load';
        loadBtn.addEventListener('click', () => {
          if (tickerInput) tickerInput.value = item.ticker;
          // eps-input is locked/display-only -- deliberately NOT restored from the record.
          // Legacy/CLI-saved records can carry an epsOverride, but the web UI no longer has an
          // override path (handleSubmit never sends the field at all), so writing it
          // here would only flash a value the server will never use before handleSubmit below
          // overwrites the field with the live data.epsTtm anyway.
          const loadData = item.base || item; // Use base for loading inputs if new, otherwise legacy
          if (growthInput) {
            growthInput.value =
              loadData.growthRatePercent !== null && loadData.growthRatePercent !== undefined
                ? Number(Number(loadData.growthRatePercent).toFixed(2))
                : '';
          }
          if (exitPeInput) exitPeInput.value = loadData.exitPeMultiple;
          if (requiredReturnInput) requiredReturnInput.value = loadData.requiredReturnPercent;
          if (yearsInput) yearsInput.value = item.years;
          if (mosSelect && loadData.mosPercent !== undefined)
            mosSelect.value = String(loadData.mosPercent);
          // Bear/bull rows: restore the saved values (growth, exit P/E, req. return) on a
          // new-shaped record, otherwise leave the current defaults in place (a legacy record
          // has no bear/bull data to load). MoS is shared -- already restored above via mosSelect.
          if (item.bear) {
            if (
              bearGrowthInput &&
              item.bear.growthRatePercent !== null &&
              item.bear.growthRatePercent !== undefined
            ) {
              bearGrowthInput.value = Number(Number(item.bear.growthRatePercent).toFixed(2));
            }
            if (bearExitPeInput && item.bear.exitPeMultiple !== undefined)
              bearExitPeInput.value = item.bear.exitPeMultiple;
            if (bearRequiredReturnInput && item.bear.requiredReturnPercent !== undefined)
              bearRequiredReturnInput.value = item.bear.requiredReturnPercent;
          }
          if (item.bull) {
            if (
              bullGrowthInput &&
              item.bull.growthRatePercent !== null &&
              item.bull.growthRatePercent !== undefined
            ) {
              bullGrowthInput.value = Number(Number(item.bull.growthRatePercent).toFixed(2));
            }
            if (bullExitPeInput && item.bull.exitPeMultiple !== undefined)
              bullExitPeInput.value = item.bull.exitPeMultiple;
            if (bullRequiredReturnInput && item.bull.requiredReturnPercent !== undefined)
              bullRequiredReturnInput.value = item.bull.requiredReturnPercent;
          }
          if (notesInput) notesInput.value = item.notes || '';
          window.scrollTo({ top: 0, behavior: 'smooth' });
          handleSubmit(new Event('submit'));
        });

        const delBtn = document.createElement('button');
        delBtn.type = 'button';
        delBtn.className = 'btn-action-del';
        delBtn.textContent = 'Delete';
        delBtn.addEventListener('click', async () => {
          try {
            const evaluatorParam = evaluatorSelect ? `?evaluator=${encodeURIComponent(evaluatorSelect.value)}` : '';
            await fetch(`/api/history/${encodeURIComponent(item.id)}${evaluatorParam}`, { method: 'DELETE' });
            const filterVal = historyFilter ? historyFilter.value : '';
            fetchHistory(filterVal);
          } catch (err) {
            console.error('Failed to delete history item:', err);
          }
        });

        tdActions.append(loadBtn, delBtn);
        tr.append(tdActions);
      }

      historyTbody.append(tr);
    }
  }
}

async function handleSaveValuation() {
  if (!currentValuation) return;
  if (saveBtn) saveBtn.disabled = true;
  if (saveStatus) {
    saveStatus.textContent = 'Saving...';
    saveStatus.className = 'save-status';
  }

  if (notesInput) {
    currentValuation.notes = notesInput.value.trim();
  }
  if (evaluatorSelect) {
    currentValuation.evaluator = evaluatorSelect.value;
  }

  try {
    const response = await fetch('/api/history', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(currentValuation),
    });
    const body = await response.json().catch(() => ({ ok: false }));

    if (response.ok && body.ok) {
      if (saveStatus) {
        saveStatus.textContent = '✓ Valuation saved!';
        saveStatus.className = 'save-status good';
      }
      setTimeout(() => {
        if (saveStatus) saveStatus.textContent = '';
      }, 3000);
      const filterVal = historyFilter ? historyFilter.value : '';
      fetchHistory(filterVal);
    } else {
      const errMsg =
        (body && body.error && body.error.message) ||
        (body && body.error && body.error.reason) ||
        (body && body.message) ||
        'Failed to save.';
      if (saveStatus) {
        saveStatus.textContent = errMsg;
        saveStatus.className = 'save-status bad';
      }
    }
  } catch (err) {
    if (saveStatus) {
      saveStatus.textContent = `Error: ${err instanceof Error ? err.message : String(err)}`;
      saveStatus.className = 'save-status bad';
    }
  } finally {
    if (saveBtn) saveBtn.disabled = false;
  }
}

// ---------------- Form Submit ----------------

async function handleSubmit(event, forceRefresh = false) {
  if (event && event.preventDefault) event.preventDefault();
  clearError();
  setLoading(true);
  if (saveStatus) saveStatus.textContent = '';

  const requestId = ++latestValuateRequestId;

  const ticker = tickerInput ? tickerInput.value.trim() : '';
  // No epsOverride is ever sent: eps-input is locked (readonly/disabled) and only ever
  // displays the live TTM EPS the server returned. A disabled input still retains a
  // JS-assigned value, so reading it back would silently resend a stale EPS from a previous
  // ticker lookup once the field had been populated below. The server treats an absent
  // epsOverride as "use data.epsTtm", which is exactly what the locked field shows.
  const growthRatePercent =
    growthInput && growthInput.value !== '' ? Number(growthInput.value) : null;
  const exitPeMultiple = exitPeInput ? Number(exitPeInput.value) : 15;
  const requiredReturnPercent = requiredReturnInput ? Number(requiredReturnInput.value) : 15;
  const years = yearsInput ? Number(yearsInput.value) : 10;
  const mosPercent = mosSelect ? Number(mosSelect.value) : 0;
  const bearGrowthRatePercent =
    bearGrowthInput && bearGrowthInput.value !== '' ? Number(bearGrowthInput.value) : null;
  const bearExitPeMultiple = bearExitPeInput ? Number(bearExitPeInput.value) : 10;
  const bearRequiredReturnPercent = bearRequiredReturnInput
    ? Number(bearRequiredReturnInput.value)
    : 15;
  const bullGrowthRatePercent =
    bullGrowthInput && bullGrowthInput.value !== '' ? Number(bullGrowthInput.value) : null;
  const bullExitPeMultiple = bullExitPeInput ? Number(bullExitPeInput.value) : 20;
  const bullRequiredReturnPercent = bullRequiredReturnInput
    ? Number(bullRequiredReturnInput.value)
    : 12;

  try {
    const response = await fetch('/api/valuate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ticker,
        growthRatePercent,
        exitPeMultiple,
        requiredReturnPercent,
        years,
        mosPercent,
        bearGrowthRatePercent,
        bearExitPeMultiple,
        bearRequiredReturnPercent,
        bullGrowthRatePercent,
        bullExitPeMultiple,
        bullRequiredReturnPercent,
        forceRefresh,
      }),
    });
    const body = await response.json();

    // A newer lookup started while this one was in flight: its result is already on screen, so
    // this stale response must not repaint anything.
    if (requestId !== latestValuateRequestId) return;

    if (!body.ok) {
      showError(formatStockDataError(body.error));
      return;
    }

    const { data, effectiveEps, lynch, ruleOne } = body;

    // Server seeds growth from the same fallback chain as the CLI when the field was left
    // blank (analystEstimate5y ?? historical3y ?? historical1y, no extra cap); it returns
    // effectiveGrowth so the UI can show the exact value used, including null when no source
    // was available at all (lynch/ruleOne will then report MISSING_GROWTH_RATE below).
    let effectiveGrowth = body.effectiveGrowth ?? growthRatePercent;
    if (effectiveGrowth !== null && effectiveGrowth !== undefined) {
      effectiveGrowth = Number(Number(effectiveGrowth).toFixed(2));
    }

    // eps-input is locked/display-only -- always show the live TTM EPS the server just used.
    // effectiveEps (not data.epsTtm) reflects resolveEpsWithFallback's result -- when Twelve
    // Data's own figure looked stale and Yahoo's was available, this is Yahoo's, not Twelve
    // Data's raw figure. See renderPriceBanner above for the source label shown alongside it.
    if (epsInput) {
      epsInput.value =
        effectiveEps !== null && effectiveEps !== undefined
          ? Number(Number(effectiveEps).toFixed(2))
          : '';
    }

    // Populate the growth input if the user left it empty, so they see the exact seed used.
    if (growthInput && growthInput.value === '') {
      growthInput.value = effectiveGrowth !== null ? effectiveGrowth : '';
    }

    // Bear/bull growth are independently editable, but when a row is left blank the server
    // still derives it from the base scenario (0.75x/1.25x) -- populate the field with that
    // derived value afterwards, same pattern as the base growth input above, so the user sees
    // exactly what was used rather than an empty box next to a real fair value. body.bearGrowth/
    // body.bullGrowth are the RAW (unclamped) values the server actually used, echoed back
    // regardless of whether lynch/ruleOne succeeded for that scenario -- deriving this from
    // ruleOne.bear.inputs/lynch.bear.inputs instead used to lose the value entirely when BOTH
    // failed for unrelated reasons (e.g. ruleOne rejecting an emptied exit-P/E while lynch
    // simultaneously rejected this same negative growth rate), since neither carries `inputs`
    // on a failed ValuationResult.
    const bearGrowthUsed = body.bearGrowth ?? null;
    if (bearGrowthInput && bearGrowthInput.value === '' && bearGrowthUsed !== null) {
      bearGrowthInput.value = Number(Number(bearGrowthUsed).toFixed(2));
    }
    const bullGrowthUsed = body.bullGrowth ?? null;
    if (bullGrowthInput && bullGrowthInput.value === '' && bullGrowthUsed !== null) {
      bullGrowthInput.value = Number(Number(bullGrowthUsed).toFixed(2));
    }

    // Cache current valuation state for saving
    currentValuation = {
      ticker: data.ticker,
      currentPrice: data.currentPrice,
      currency: data.currency,
      // effectiveEps, not data.epsTtm -- reflects resolveEpsWithFallback's result, so a saved
      // record matches the number actually shown/used, not a stale Twelve Data figure the UI
      // itself already replaced.
      epsTtm: effectiveEps,
      // No epsOverride key: the field is locked and handleSubmit never sends one, so a
      // web-saved record always reflects the live TTM EPS. Legacy/CLI records may still carry
      // epsOverride, which renderHistoryTable continues to honour when displaying them.
      years,

      base: {
        growthRatePercent: effectiveGrowth,
        exitPeMultiple: exitPeMultiple,
        requiredReturnPercent: requiredReturnPercent,
        mosPercent: mosPercent,
        lynchFairValue: lynch.base.ok ? lynch.base.fairValue : null,
        ruleOneFairValue: ruleOne.base.ok ? ruleOne.base.fairValue : null,
      },
      // exitPeMultiple/requiredReturnPercent below are read from what the user actually typed
      // into the Bear/Bull rows (not hardcoded) -- see the ruleOne.*.inputs the server echoes
      // back, which reflect exactly what was sent in the request. mosPercent is the single
      // shared value from the top row -- there is no separate bear/bull MoS.
      bear: {
        // Raw (unclamped), matching base's own save above (effectiveGrowth), and matching the
        // exact value the input backfill above just used -- saving the clamped value here would
        // mean reloading this record later re-populates the input with the clamp boundary
        // instead of the growth that actually produced this result.
        growthRatePercent: bearGrowthUsed,
        exitPeMultiple: bearExitPeMultiple,
        requiredReturnPercent: bearRequiredReturnPercent,
        mosPercent: mosPercent,
        lynchFairValue: lynch.bear.ok ? lynch.bear.fairValue : null,
        ruleOneFairValue: ruleOne.bear.ok ? ruleOne.bear.fairValue : null,
      },
      bull: {
        growthRatePercent: bullGrowthUsed,
        exitPeMultiple: bullExitPeMultiple,
        requiredReturnPercent: bullRequiredReturnPercent,
        mosPercent: mosPercent,
        lynchFairValue: lynch.bull.ok ? lynch.bull.fairValue : null,
        ruleOneFairValue: ruleOne.bull.ok ? ruleOne.bull.fairValue : null,
      },
      notes: notesInput ? notesInput.value.trim() : '',
    };

    renderGrowthChips(data.growth);
    renderPriceBanner(data, lynch.base, ruleOne.base, effectiveEps, body.epsSource, body.epsSourceDetail);
    renderGrowthTable(data.growth, effectiveGrowth);
    renderMultiplesTable(data, effectiveGrowth, effectiveEps, body.analystConsensus);
    renderAnalystTable(body.analystConsensus, data.currentPrice);

    renderMethodCard('lynch', lynch, data.currentPrice);

    // exit P/E / req. return shown per scenario come from what the server actually used
    // (scenarioResult.inputs, which echoes the exact bear/bull row values sent in the request)
    // -- never hardcoded here, so they can never drift from the real inputs behind the number.
    // MoS is the single shared value from the top row -- same for all three scenarios.
    const scenarioAssumptions = {
      bear: { exitPe: bearExitPeMultiple, reqRet: bearRequiredReturnPercent, mos: mosPercent },
      base: { exitPe: exitPeMultiple, reqRet: requiredReturnPercent, mos: mosPercent },
      bull: { exitPe: bullExitPeMultiple, reqRet: bullRequiredReturnPercent, mos: mosPercent },
    };
    renderMethodCard('rule-one', ruleOne, data.currentPrice, (scenarioName, scenarioResult) => {
      const fallback = scenarioAssumptions[scenarioName];
      const inputs = scenarioResult.ok ? scenarioResult.inputs : {};
      const exitPe = inputs.exitPeMultiple ?? fallback.exitPe;
      const reqRet = inputs.requiredReturnPercent ?? fallback.reqRet;
      const mos = inputs.mosPercent ?? fallback.mos;

      const extras = [
        ['exit P/E', fmt(exitPe)],
        ['req. return', `${fmt(reqRet)}%`],
        ['years', years],
      ];
      if (mos > 0) {
        extras.push(['MoS', `${mos}%`]);
        if (scenarioResult.intermediate && scenarioResult.intermediate.stickerPrice) {
          extras.push(['sticker', fmt(scenarioResult.intermediate.stickerPrice)]);
        }
      }
      return extras;
    });

    if (result) result.hidden = false;
  } catch (err) {
    if (requestId !== latestValuateRequestId) return;
    showError(`Request failed: ${err instanceof Error ? err.message : String(err)}`);
  } finally {
    // Only the newest request owns the loading state; a superseded one must not re-enable the
    // form while its replacement is still running.
    if (requestId === latestValuateRequestId) setLoading(false);
  }
}

// Event Listeners
const valuateForm = document.getElementById('valuate-form');
if (valuateForm) valuateForm.addEventListener('submit', (e) => handleSubmit(e, false));

if (tickerInput) {
  tickerInput.addEventListener('input', () => {
    if (epsInput) epsInput.value = '';
    if (growthInput) growthInput.value = '';
    if (bearGrowthInput) bearGrowthInput.value = '';
    if (bullGrowthInput) bullGrowthInput.value = '';
  });
}

if (refreshBtn) {
  refreshBtn.addEventListener('click', (e) => {
    handleSubmit(e, true);
  });
}
if (saveBtn) saveBtn.addEventListener('click', handleSaveValuation);
if (historyRefreshBtn) {
  historyRefreshBtn.addEventListener('click', () => {
    fetchHistory(historyFilter ? historyFilter.value : '');
  });
}
if (historyFilter) {
  historyFilter.addEventListener('input', () => {
    fetchHistory(historyFilter.value);
  });
}
if (evaluatorSelect) {
  evaluatorSelect.addEventListener('change', () => {
    fetchHistory(historyFilter ? historyFilter.value : '');
  });
}

function renderEvaluators() {
  if (!evaluatorSelect) return;
  const list = JSON.parse(localStorage.getItem('evaluatorsList')) || ['Aviv', 'Ran'];
  const currentVal = evaluatorSelect.value;
  evaluatorSelect.innerHTML = '';
  list.forEach(name => {
    const opt = document.createElement('option');
    opt.value = name;
    opt.textContent = name;
    evaluatorSelect.appendChild(opt);
  });
  if (list.includes(currentVal)) {
    evaluatorSelect.value = currentVal;
  }
}

if (addEvaluatorBtn) {
  addEvaluatorBtn.addEventListener('click', () => {
    const name = prompt('Enter new evaluator name:');
    if (name && name.trim()) {
      const list = JSON.parse(localStorage.getItem('evaluatorsList')) || ['Aviv', 'Ran'];
      if (!list.includes(name.trim())) {
        list.push(name.trim());
        localStorage.setItem('evaluatorsList', JSON.stringify(list));
        renderEvaluators();
        evaluatorSelect.value = name.trim();
        evaluatorSelect.dispatchEvent(new Event('change'));
      }
    }
  });
}

if (delEvaluatorBtn) {
  delEvaluatorBtn.addEventListener('click', () => {
    const name = evaluatorSelect.value;
    if (!name) return;
    if (confirm(`Remove ${name} from the dropdown? (History files are not deleted)`)) {
      let list = JSON.parse(localStorage.getItem('evaluatorsList')) || ['Aviv', 'Ran'];
      list = list.filter(n => n !== name);
      localStorage.setItem('evaluatorsList', JSON.stringify(list));
      renderEvaluators();
      evaluatorSelect.dispatchEvent(new Event('change'));
    }
  });
}

renderEvaluators();

// Initial history load
fetchHistory();
