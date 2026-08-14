// Plain script, no bundler/framework. Talks to POST /api/valuate only — no valuation math here,
// that would reimplement the formulas the same way the base design doc forbids in the CLI.

const tickerInput = document.getElementById('ticker-input');
const goBtn = document.getElementById('go-btn');
const growthInput = document.getElementById('growth-input');
const exitPeInput = document.getElementById('exit-pe-input');
const requiredReturnInput = document.getElementById('required-return-input');
const yearsInput = document.getElementById('years-input');
const growthChips = document.getElementById('growth-chips');
const statStrip = document.getElementById('stat-strip');
const errorCard = document.getElementById('error-card');
const cards = document.getElementById('cards');
const referenceStrip = document.getElementById('reference-strip');

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

function setLoading(isLoading) {
  goBtn.disabled = isLoading;
  cards.style.opacity = isLoading ? '0.5' : '1';
}

function showError(message) {
  statStrip.hidden = true;
  cards.hidden = true;
  referenceStrip.hidden = true;
  errorCard.hidden = false;
  errorCard.textContent = message;
}

function clearError() {
  errorCard.hidden = true;
}

function statBlock(label, value) {
  const div = document.createElement('div');
  const labelDiv = document.createElement('div');
  labelDiv.className = 'stat-label';
  labelDiv.textContent = label;
  const valueDiv = document.createElement('div');
  valueDiv.className = 'stat-value';
  valueDiv.textContent = value;
  div.append(labelDiv, valueDiv);
  return div;
}

function renderStatStrip(data, growthUsed) {
  statStrip.innerHTML = '';
  statStrip.append(
    statBlock('Ticker', data.ticker),
    statBlock('Current price', `${fmt(data.currentPrice)} ${data.currency}`),
    statBlock('EPS (TTM)', fmt(data.epsTtm)),
    statBlock('Growth rate used', `${fmt(growthUsed)}%`),
  );
  statStrip.hidden = false;
}

function renderReference(data) {
  referenceStrip.innerHTML = '';
  referenceStrip.append(
    statBlock('Hist. P/E 1y', fmt(data.historicalPe.avg1y)),
    statBlock('Hist. P/E 3y', fmt(data.historicalPe.avg3y)),
    statBlock('Hist. P/E 5y', fmt(data.historicalPe.avg5y)),
    statBlock('Trailing P/E · PEG (reference only)', `${fmt(data.providerReference.trailingPe)} · ${fmt(data.providerReference.pegRatio)}`),
  );
  referenceStrip.hidden = false;
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

    if (growthInput.value === '') {
      const seed =
        data.growth.analystEstimate5yPercent ??
        data.growth.historical3yPercent ??
        data.growth.historical1yPercent ??
        '';
      growthInput.value = seed;
    }

    renderGrowthChips(data.growth);
    renderStatStrip(data, growthRatePercent);
    renderReference(data);

    renderMethodCard('lynch', lynch, data.currentPrice);
    renderMethodCard('rule-one', ruleOne, data.currentPrice, [
      ['exit P/E', fmt(exitPeMultiple)],
      ['req. return', `${fmt(requiredReturnPercent)}%`],
      ['years', years],
    ]);

    cards.hidden = false;
  } catch (err) {
    showError(`Request failed: ${err instanceof Error ? err.message : String(err)}`);
  } finally {
    setLoading(false);
  }
}

document.getElementById('valuate-form').addEventListener('submit', handleSubmit);
