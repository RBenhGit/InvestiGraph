// Plain script, no bundler/framework. Talks to POST /api/valuate only -- no valuation math here,
// that would reimplement the formulas the same way the base design doc forbids in the CLI.

const tickerInput = document.getElementById('ticker-input');
const epsInput = document.getElementById('eps-input');
const goBtn = document.getElementById('go-btn');
const growthInput = document.getElementById('growth-input');
const exitPeInput = document.getElementById('exit-pe-input');
const requiredReturnInput = document.getElementById('required-return-input');
const yearsInput = document.getElementById('years-input');
const mosSelect = document.getElementById('mos-select');
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
const saveBtn = document.getElementById('save-btn');
const saveStatus = document.getElementById('save-status');
const historyEmpty = document.getElementById('history-empty');
const historyTableContainer = document.getElementById('history-table-container');
const historyTbody = document.getElementById('history-tbody');
const historyFilter = document.getElementById('history-filter');
const historyRefreshBtn = document.getElementById('history-refresh-btn');

let currentValuation = null;

// ---------------- Scenario Management ----------------
let currentScenario = 'base';
const scenarioState = {
  base: { growth: null, exitPe: 15, requiredReturn: 15, years: 10, mos: 25 },
  bull: { growth: null, exitPe: 20, requiredReturn: 12, years: 10, mos: 10 },
  bear: { growth: null, exitPe: 10, requiredReturn: 15, years: 10, mos: 50 },
};

function saveCurrentScenarioInputs() {
  if (!scenarioState[currentScenario]) return;
  if (growthInput && growthInput.value !== '') {
    scenarioState[currentScenario].growth = Number(growthInput.value);
  }
  if (exitPeInput) {
    scenarioState[currentScenario].exitPe = Number(exitPeInput.value) || 15;
  }
  if (requiredReturnInput) {
    scenarioState[currentScenario].requiredReturn = Number(requiredReturnInput.value) || 15;
  }
  if (yearsInput) {
    scenarioState[currentScenario].years = Number(yearsInput.value) || 10;
  }
  if (mosSelect) {
    scenarioState[currentScenario].mos = Number(mosSelect.value) || 0;
  }
}

function applyScenario(targetScenario) {
  saveCurrentScenarioInputs();
  currentScenario = targetScenario;

  const buttons = document.querySelectorAll('.scenario-btn');
  buttons.forEach((btn) => {
    if (btn.getAttribute('data-scenario') === targetScenario) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });

  const state = scenarioState[targetScenario];
  if (!state) return;

  if (state.growth === null && scenarioState.base.growth !== null) {
    const baseG = scenarioState.base.growth;
    if (targetScenario === 'bull') {
      state.growth = Number((baseG > 0 ? baseG * 1.25 : baseG + 3).toFixed(2));
    } else if (targetScenario === 'bear') {
      state.growth = Number((baseG > 0 ? baseG * 0.75 : baseG - 3).toFixed(2));
    }
  }

  if (growthInput && state.growth !== null) growthInput.value = state.growth;
  if (exitPeInput) exitPeInput.value = state.exitPe;
  if (requiredReturnInput) requiredReturnInput.value = state.requiredReturn;
  if (yearsInput) yearsInput.value = state.years;
  if (mosSelect) mosSelect.value = String(state.mos);

  if (tickerInput && tickerInput.value.trim() !== '') {
    handleSubmit(new Event('submit'));
  }
}

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

  if (fairValue === null || fairValue === undefined || Number.isNaN(fairValue)) {
    valueDiv.textContent = 'n/a';
  } else {
    const diffPercent = (fairValue / currentPrice - 1) * 100;
    const undervalued = diffPercent > 0;
    valueDiv.innerHTML = `<b>${fmt(fairValue)}</b> <span class="${undervalued ? 'good' : 'bad'}">${undervalued ? '+' : ''}${fmt(diffPercent)}%</span>`;
  }

  div.append(labelDiv, valueDiv);
  return div;
}

function renderPriceBanner(data, lynch, ruleOne) {
  if (!priceValueEl || !priceMetaEl || !priceDeltasEl) return;
  priceValueEl.textContent = `${fmt(data.currentPrice)} ${data.currency}`;
  priceMetaEl.textContent = `${data.ticker} · EPS (TTM) ${fmt(data.epsTtm)} · as of ${data.asOf}`;

  priceDeltasEl.innerHTML = '';
  priceDeltasEl.append(
    renderPriceDelta('Peter Lynch fair value', lynch.ok ? lynch.fairValue : null, data.currentPrice, '--accent-a'),
    renderPriceDelta('Rule #1 fair value', ruleOne.ok ? ruleOne.fairValue : null, data.currentPrice, '--accent-b'),
  );
}

/** Small label/value row for the growth-sources and multiples panels. */
function tableRow(label, value, opts) {
  const row = document.createElement('div');
  row.className = 'mini-row';
  const labelDiv = document.createElement('div');
  labelDiv.className = 'mini-label';
  labelDiv.textContent = label;
  const valueDiv = document.createElement('div');
  valueDiv.className = 'mini-value';
  valueDiv.textContent = value;
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
  const epsToUse = (effectiveEps && effectiveEps > 0) ? effectiveEps : data.epsTtm;
  const trailingPe = (epsToUse && epsToUse > 0) ? (currentPrice / epsToUse) : null;
  
  // Calculate local PEG instead of relying on provider's unreliable metric
  let pegRatio = null;
  if (trailingPe !== null && effectiveGrowth !== null && effectiveGrowth > 0) {
    pegRatio = trailingPe / effectiveGrowth;
  }

  multiplesTableEl.append(
    tableRow('Median P/E, 1Y', fmt(data.historicalPe.avg1y)),
    tableRow('Median P/E, 3Y', fmt(data.historicalPe.avg3y)),
    tableRow('Median P/E, 5Y', fmt(data.historicalPe.avg5y)),
    tableRow('Trailing P/E (current)', fmt(trailingPe)),
    tableRow('PEG ratio (local)', fmt(pegRatio)),
  );

  if (analystConsensus && analystConsensus.priceToSales !== undefined) {
    multiplesTableEl.append(
      tableRow('P/S ratio (TTM)', fmt(analystConsensus.priceToSales))
    );
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

  const { nextYearEpsGrowthPercent, priceTarget, recommendationKey, beta, ruleOf40 } = analystConsensus;

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

  // Financial Health Metrics. beta/ruleOf40 are typed `number | null` (never `undefined`) —
  // gate the section header on `!== null` too, matching the row-level checks below, so the
  // header isn't shown when both values are genuinely missing (e.g. a ticker Yahoo has no
  // summaryDetail/financialData coverage for).
  if (beta !== null || ruleOf40 !== null) {
    const divider = document.createElement('tr');
    divider.innerHTML = '<td colspan="2" style="padding-top: 1rem; border-bottom: 1px solid var(--border); font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); font-weight: 600;">Financial Health</td>';
    analystTableEl.append(divider);

    if (ruleOf40 !== undefined && ruleOf40 !== null) {
      analystTableEl.append(tableRow('Rule of 40', `${fmt(ruleOf40)}%`));
    }
    if (beta !== undefined && beta !== null) {
      analystTableEl.append(tableRow('Beta (Volatility)', fmt(beta)));
    }
  }
}

function priceTargetValue(target, currentPrice) {
  if (target === null || target === undefined) return 'n/a';
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
        growthInput.value = value;
        scenarioState[currentScenario].growth = value;
      }
    });
    growthChips.append(chip);
  }
}

function renderVerdict(el, fairValue, currentPrice) {
  const undervalued = fairValue > currentPrice;
  el.textContent = undervalued ? 'Undervalued' : 'Overvalued';
  el.className = `verdict ${undervalued ? 'good' : 'bad'}`;
}

function growthIO(inputs) {
  const raw = inputs.growthRatePercentRaw;
  const clamped = inputs.growthRatePercentClamped;
  if (raw !== clamped) {
    return `<span class="io"><span class="raw">${fmt(raw)}%</span><b class="clamped">${fmt(clamped)}%</b></span>`;
  }
  return `<span class="io">growth: <b>${fmt(clamped)}%</b></span>`;
}

function renderMethodCard(prefix, result, currentPrice, extraFields) {
  const fairValueEl = document.getElementById(`${prefix}-fair-value`);
  const verdictEl = document.getElementById(`${prefix}-verdict`);
  const inputsEl = document.getElementById(`${prefix}-inputs`);

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

  const extraHtml = (extraFields || [])
    .map(([label, value]) => `<span class="io">${label}: <b>${value}</b></span>`)
    .join('');
  inputsEl.innerHTML = growthIO(result.inputs) + extraHtml;
}

// ---------------- History Functions ----------------

async function fetchHistory(filterTicker) {
  if (!historyTbody) return;
  try {
    const url = filterTicker && filterTicker.trim()
      ? `/api/history?ticker=${encodeURIComponent(filterTicker.trim())}`
      : '/api/history';
    const response = await fetch(url);
    const body = await response.json();

    if (!body || !body.ok) return;

    renderHistoryTable(body.data);
  } catch (err) {
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
    const tr = document.createElement('tr');

    // Date
    const tdDate = document.createElement('td');
    tdDate.className = 'table-date';
    tdDate.textContent = formatDate(item.evaluatedAt);

    // Ticker
    const tdTicker = document.createElement('td');
    const badge = document.createElement('span');
    badge.className = 'badge-ticker';
    badge.textContent = item.ticker;
    tdTicker.append(badge);

    // Price
    const tdPrice = document.createElement('td');
    tdPrice.className = 'table-price';
    tdPrice.textContent = `${fmt(item.currentPrice)} ${item.currency || 'USD'}`;

    // Lynch Fair Value
    const tdLynch = document.createElement('td');
    tdLynch.className = 'table-val';
    if (item.lynchFairValue !== null && item.lynchFairValue !== undefined) {
      const diff = (item.lynchFairValue / item.currentPrice - 1) * 100;
      const isGood = diff > 0;
      tdLynch.innerHTML = `<b>${fmt(item.lynchFairValue)}</b> <span class="${isGood ? 'good' : 'bad'}">(${isGood ? '+' : ''}${fmt(diff)}%)</span>`;
    } else {
      tdLynch.textContent = 'n/a';
    }

    // Rule #1 Fair Value
    const tdRuleOne = document.createElement('td');
    tdRuleOne.className = 'table-val';
    if (item.ruleOneFairValue !== null && item.ruleOneFairValue !== undefined) {
      const diff = (item.ruleOneFairValue / item.currentPrice - 1) * 100;
      const isGood = diff > 0;
      tdRuleOne.innerHTML = `<b>${fmt(item.ruleOneFairValue)}</b> <span class="${isGood ? 'good' : 'bad'}">(${isGood ? '+' : ''}${fmt(diff)}%)</span>`;
    } else {
      tdRuleOne.textContent = 'n/a';
    }

    // Growth
    const tdGrowth = document.createElement('td');
    tdGrowth.className = 'table-val';
    tdGrowth.textContent = fmtPercent(item.growthRatePercent);

    // Assumptions
    const tdAssump = document.createElement('td');
    tdAssump.className = 'table-assumptions';
    const mosText = item.mosPercent ? ` | MoS: ${item.mosPercent}%` : '';
    const epsText = item.epsOverride ? ` | Adj.EPS: ${fmt(item.epsOverride)}` : '';
    tdAssump.textContent = `PE: ${fmt(item.exitPeMultiple)} | Req: ${fmt(item.requiredReturnPercent)}% | ${item.years}y${mosText}${epsText}`;

    // Notes
    const tdNotes = document.createElement('td');
    tdNotes.className = 'table-notes';
    tdNotes.textContent = item.notes || '—';
    if (item.notes) tdNotes.title = item.notes;

    // Actions
    const tdActions = document.createElement('td');
    tdActions.className = 'table-actions';

    const loadBtn = document.createElement('button');
    loadBtn.type = 'button';
    loadBtn.className = 'btn-action-load';
    loadBtn.textContent = 'Load';
    loadBtn.addEventListener('click', () => {
      if (tickerInput) tickerInput.value = item.ticker;
      if (epsInput) {
        epsInput.value = item.epsOverride !== undefined && item.epsOverride !== null ? item.epsOverride : '';
      }
      if (growthInput) growthInput.value = item.growthRatePercent;
      if (exitPeInput) exitPeInput.value = item.exitPeMultiple;
      if (requiredReturnInput) requiredReturnInput.value = item.requiredReturnPercent;
      if (yearsInput) yearsInput.value = item.years;
      if (mosSelect && item.mosPercent !== undefined) mosSelect.value = String(item.mosPercent);
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
        await fetch(`/api/history/${encodeURIComponent(item.id)}`, { method: 'DELETE' });
        const filterVal = historyFilter ? historyFilter.value : '';
        fetchHistory(filterVal);
      } catch (err) {
        console.error('Failed to delete history item:', err);
      }
    });

    tdActions.append(loadBtn, delBtn);

    tr.append(tdDate, tdTicker, tdPrice, tdLynch, tdRuleOne, tdGrowth, tdAssump, tdNotes, tdActions);
    historyTbody.append(tr);
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

  const ticker = tickerInput ? tickerInput.value.trim() : '';
  const epsOverride = epsInput && epsInput.value !== '' ? Number(epsInput.value) : undefined;
  const growthRatePercent = growthInput && growthInput.value !== '' ? Number(growthInput.value) : null;
  const exitPeMultiple = exitPeInput ? Number(exitPeInput.value) : 15;
  const requiredReturnPercent = requiredReturnInput ? Number(requiredReturnInput.value) : 15;
  const years = yearsInput ? Number(yearsInput.value) : 10;
  const mosPercent = mosSelect ? Number(mosSelect.value) : 0;

  try {
    const response = await fetch('/api/valuate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ticker,
        epsOverride,
        growthRatePercent,
        exitPeMultiple,
        requiredReturnPercent,
        years,
        mosPercent,
        forceRefresh,
      }),
    });
    const body = await response.json();

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

    // Show the actual EPS used if the user left it on Auto
    if (epsInput && epsInput.value === '') {
      epsInput.value = data.epsTtm;
    }

    // Populate the growth input if the user left it empty, so they see the exact seed used.
    if (growthInput && growthInput.value === '') {
      growthInput.value = effectiveGrowth !== null ? effectiveGrowth : '';
      scenarioState.base.growth = effectiveGrowth;
    }

    // Cache current valuation state for saving
    currentValuation = {
      ticker: data.ticker,
      currentPrice: data.currentPrice,
      currency: data.currency,
      epsTtm: data.epsTtm,
      epsOverride,
      growthRatePercent: effectiveGrowth,
      exitPeMultiple,
      requiredReturnPercent,
      years,
      mosPercent,
      lynchFairValue: lynch.ok ? lynch.fairValue : null,
      ruleOneFairValue: ruleOne.ok ? ruleOne.fairValue : null,
      notes: notesInput ? notesInput.value.trim() : '',
    };

    renderGrowthChips(data.growth);
    renderPriceBanner(data, lynch, ruleOne);
    renderGrowthTable(data.growth, effectiveGrowth);
    renderMultiplesTable(data, effectiveGrowth, effectiveEps, body.analystConsensus);
    renderAnalystTable(body.analystConsensus, data.currentPrice);

    renderMethodCard('lynch', lynch, data.currentPrice);
    const ruleOneExtras = [
      ['exit P/E', fmt(exitPeMultiple)],
      ['req. return', `${fmt(requiredReturnPercent)}%`],
      ['years', years],
    ];
    if (mosPercent > 0) {
      ruleOneExtras.push(['MoS', `${mosPercent}%`]);
      if (ruleOne.intermediate && ruleOne.intermediate.stickerPrice) {
        ruleOneExtras.push(['sticker', fmt(ruleOne.intermediate.stickerPrice)]);
      }
    }
    renderMethodCard('rule-one', ruleOne, data.currentPrice, ruleOneExtras);

    if (result) result.hidden = false;
  } catch (err) {
    showError(`Request failed: ${err instanceof Error ? err.message : String(err)}`);
  } finally {
    setLoading(false);
  }
}

// Event Listeners
const valuateForm = document.getElementById('valuate-form');
if (valuateForm) valuateForm.addEventListener('submit', (e) => handleSubmit(e, false));

if (tickerInput) {
  tickerInput.addEventListener('input', () => {
    if (epsInput) epsInput.value = '';
    // Optional: clear growth if desired, but for now just clear EPS so it doesn't leak between stocks
  });
}

const refreshBtn = document.getElementById('refresh-btn');
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

// Scenario buttons
const scenarioButtons = document.querySelectorAll('.scenario-btn');
scenarioButtons.forEach((btn) => {
  btn.addEventListener('click', () => {
    const scenario = btn.getAttribute('data-scenario');
    if (scenario) applyScenario(scenario);
  });
});

// Initial history load
fetchHistory();
