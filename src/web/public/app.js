// Plain script, no bundler/framework. Talks to POST /api/valuate only -- no valuation math here,
// that would reimplement the formulas the same way the base design doc forbids in the CLI.

const tickerInput = document.getElementById('ticker-input');
const goBtn = document.getElementById('go-btn');
const growthInput = document.getElementById('growth-input');
const exitPeInput = document.getElementById('exit-pe-input');
const requiredReturnInput = document.getElementById('required-return-input');
const yearsInput = document.getElementById('years-input');
const growthChips = document.getElementById('growth-chips');
const errorCard = document.getElementById('error-card');
const result = document.getElementById('result');
const cards = document.getElementById('cards');
const priceValueEl = document.getElementById('price-value');
const priceMetaEl = document.getElementById('price-meta');
const priceDeltasEl = document.getElementById('price-deltas');
const growthTableEl = document.getElementById('growth-table');
const multiplesTableEl = document.getElementById('multiples-table');

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

function setLoading(isLoading) {
  goBtn.disabled = isLoading;
  result.style.opacity = isLoading ? '0.5' : '1';
}

function showError(message) {
  result.hidden = true;
  errorCard.hidden = false;
  errorCard.textContent = message;
}

function clearError() {
  errorCard.hidden = true;
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
  priceValueEl.textContent = `${fmt(data.currentPrice)} ${data.currency}`;
  priceMetaEl.textContent = `${data.ticker} \u00b7 EPS (TTM) ${fmt(data.epsTtm)} \u00b7 as of ${data.asOf}`;

  priceDeltasEl.innerHTML = '';
  priceDeltasEl.append(
    renderPriceDelta('Lynch fair value', lynch.ok ? lynch.fairValue : null, data.currentPrice, '--accent-a'),
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
  return row;
}

/** Every EPS growth-rate source side by side, with the one currently in use highlighted --
 * replaces the old chip-only display, where picking a source hid the others. */
function renderGrowthTable(growth, growthUsed) {
  growthTableEl.innerHTML = '';
  const sources = [
    { key: 'historical1yPercent', label: 'Historical, 1Y' },
    { key: 'historical3yPercent', label: 'Historical, 3Y CAGR' },
    { key: 'historical5yPercent', label: 'Historical, 5Y' },
    { key: 'analystEstimate5yPercent', label: 'Analyst estimate, 5Y' },
  ];
  for (const source of sources) {
    const value = growth[source.key];
    const isActive = value !== null && value !== undefined && value === growthUsed;
    growthTableEl.append(tableRow(source.label, fmtPercent(value), { highlight: isActive }));
  }
}

/** Historical average P/E (1y/3y/5y, computed locally) plus the provider's own point-in-time
 * trailing P/E and PEG -- grouped together since they all answer "is this multiple rich?". */
function renderMultiplesTable(data) {
  multiplesTableEl.innerHTML = '';
  multiplesTableEl.append(
    tableRow('Avg. P/E, 1Y', fmt(data.historicalPe.avg1y)),
    tableRow('Avg. P/E, 3Y', fmt(data.historicalPe.avg3y)),
    tableRow('Avg. P/E, 5Y', fmt(data.historicalPe.avg5y)),
    tableRow('Trailing P/E (current)', fmt(data.providerReference.trailingPe)),
    tableRow('PEG ratio', fmt(data.providerReference.pegRatio)),
  );
}

/** Growth-source chips: up to 4, one per non-null growth figure. Clicking one overwrites the
 * growth input; the field stays freely hand-editable afterward. */
function renderGrowthChips(growth) {
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
      growthInput.value = value;
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

async function handleSubmit(event) {
  event.preventDefault();
  clearError();
  setLoading(true);

  const ticker = tickerInput.value.trim();
  const growthRatePercent = Number(growthInput.value);
  const exitPeMultiple = Number(exitPeInput.value);
  const requiredReturnPercent = Number(requiredReturnInput.value);
  const years = Number(yearsInput.value);

  try {
    const response = await fetch('/api/valuate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ticker, growthRatePercent, exitPeMultiple, requiredReturnPercent, years }),
    });
    const body = await response.json();

    if (!body.ok) {
      showError(formatStockDataError(body.error));
      return;
    }

    const { data, lynch, ruleOne } = body;

    let effectiveGrowth = growthRatePercent;
    if (growthInput.value === '') {
      const seed =
        data.growth.analystEstimate5yPercent ??
        data.growth.historical3yPercent ??
        data.growth.historical1yPercent ??
        '';
      growthInput.value = seed;
      effectiveGrowth = seed === '' ? null : seed;
    }

    renderGrowthChips(data.growth);
    renderPriceBanner(data, lynch, ruleOne);
    renderGrowthTable(data.growth, effectiveGrowth);
    renderMultiplesTable(data);

    renderMethodCard('lynch', lynch, data.currentPrice);
    renderMethodCard('rule-one', ruleOne, data.currentPrice, [
      ['exit P/E', fmt(exitPeMultiple)],
      ['req. return', `${fmt(requiredReturnPercent)}%`],
      ['years', years],
    ]);

    result.hidden = false;
  } catch (err) {
    showError(`Request failed: ${err instanceof Error ? err.message : String(err)}`);
  } finally {
    setLoading(false);
  }
}

document.getElementById('valuate-form').addEventListener('submit', handleSubmit);
