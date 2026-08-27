const tbody = document.getElementById('valuations-tbody');
const filterInput = document.getElementById('filter-input');
const evaluatorFilter = document.getElementById('evaluator-filter');
const table = document.getElementById('valuations-table');
let allValuations = [];
let sortCol = 'ticker';
let sortAsc = true;

function fmt(n) {
  if (n === null || n === undefined || isNaN(n)) return 'n/a';
  return Number(n).toFixed(2);
}

function parsePct(fv, price) {
  if (fv === null || fv === undefined || price === null || price === undefined || price === 0) return null;
  return (fv / price - 1) * 100;
}

function populateEvaluatorFilter() {
  const uniqueEvaluators = [...new Set(allValuations.map(v => v.evaluator || 'Aviv'))].sort();
  const currentVal = evaluatorFilter.value;
  evaluatorFilter.innerHTML = '<option value="">All Evaluators</option>';
  for (const ev of uniqueEvaluators) {
    const opt = document.createElement('option');
    opt.value = ev.toLowerCase();
    opt.textContent = ev;
    evaluatorFilter.appendChild(opt);
  }
  evaluatorFilter.value = currentVal;
}

function renderTable() {
  const filter = filterInput.value.trim().toLowerCase();
  const evalFilter = evaluatorFilter.value;
  
  let filtered = allValuations.filter(v => {
    const evaluator = v.evaluator || 'Aviv';
    const matchesTicker = v.ticker.toLowerCase().includes(filter);
    const matchesEval = evalFilter === '' || evaluator.toLowerCase() === evalFilter;
    return matchesTicker && matchesEval;
  });

  filtered.sort((a, b) => {
    let valA, valB;
    const evaluatorA = a.evaluator || 'Aviv';
    const evaluatorB = b.evaluator || 'Aviv';
    const baseA = a.base || a;
    const baseB = b.base || b;
    
    switch(sortCol) {
      case 'ticker': valA = a.ticker; valB = b.ticker; break;
      case 'price': valA = a.currentPrice; valB = b.currentPrice; break;
      case 'lynch': valA = baseA.lynchFairValue; valB = baseB.lynchFairValue; break;
      case 'lynch-pct': valA = parsePct(baseA.lynchFairValue, a.currentPrice); valB = parsePct(baseB.lynchFairValue, b.currentPrice); break;
      case 'rule1': valA = baseA.ruleOneFairValue; valB = baseB.ruleOneFairValue; break;
      case 'rule1-pct': valA = parsePct(baseA.ruleOneFairValue, a.currentPrice); valB = parsePct(baseB.ruleOneFairValue, b.currentPrice); break;
      case 'evaluator': valA = evaluatorA; valB = evaluatorB; break;
      default: valA = a.ticker; valB = b.ticker; break;
    }

    const nullA = (valA === null || valA === undefined || valA === 'n/a');
    const nullB = (valB === null || valB === undefined || valB === 'n/a');
    
    if (nullA && nullB) return 0;
    if (nullA) return 1;
    if (nullB) return -1;
    
    if (typeof valA === 'string') {
      return sortAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
    }
    return sortAsc ? valA - valB : valB - valA;
  });

  tbody.innerHTML = '';
  for (const v of filtered) {
    const base = v.base || v;
    const evaluator = v.evaluator || 'Aviv';
    
    const tr = document.createElement('tr');
    
    // Ticker
    const tdTicker = document.createElement('td');
    const badge = document.createElement('span');
    badge.className = 'badge-ticker';
    badge.textContent = v.ticker;
    tdTicker.appendChild(badge);
    tr.appendChild(tdTicker);
    
    // Price
    const tdPrice = document.createElement('td');
    tdPrice.className = 'table-price';
    tdPrice.textContent = `${fmt(v.currentPrice)} ${v.currency || 'USD'}`;
    tr.appendChild(tdPrice);
    
    // Lynch Base
    const tdLynch = document.createElement('td');
    tdLynch.className = 'table-val';
    tdLynch.textContent = fmt(base.lynchFairValue);
    tr.appendChild(tdLynch);
    
    // Lynch Pct
    const tdLynchPct = document.createElement('td');
    tdLynchPct.className = 'table-val';
    const lPct = parsePct(base.lynchFairValue, v.currentPrice);
    if (lPct !== null) {
      const isGood = lPct > 0;
      tdLynchPct.innerHTML = `<span class="${isGood ? 'good' : 'bad'}">${isGood ? '+' : ''}${fmt(lPct)}%</span>`;
    } else {
      tdLynchPct.textContent = 'n/a';
    }
    tr.appendChild(tdLynchPct);

    // Rule 1 Base
    const tdRule1 = document.createElement('td');
    tdRule1.className = 'table-val';
    tdRule1.textContent = fmt(base.ruleOneFairValue);
    tr.appendChild(tdRule1);
    
    // Rule 1 Pct
    const tdRule1Pct = document.createElement('td');
    tdRule1Pct.className = 'table-val';
    const rPct = parsePct(base.ruleOneFairValue, v.currentPrice);
    if (rPct !== null) {
      const isGood = rPct > 0;
      tdRule1Pct.innerHTML = `<span class="${isGood ? 'good' : 'bad'}">${isGood ? '+' : ''}${fmt(rPct)}%</span>`;
    } else {
      tdRule1Pct.textContent = 'n/a';
    }
    tr.appendChild(tdRule1Pct);

    // Evaluator
    const tdEval = document.createElement('td');
    tdEval.textContent = evaluator;
    tr.appendChild(tdEval);

    tbody.appendChild(tr);
  }
}

async function fetchValuations() {
  try {
    const res = await fetch('/api/valuations');
    const body = await res.json();
    if (body.ok) {
      allValuations = body.data;
      populateEvaluatorFilter();
      renderTable(); // Initial render with cached prices
      
      // Fetch live prices in the background
      const tickers = [...new Set(allValuations.map(v => v.ticker))].filter(Boolean);
      if (tickers.length > 0) {
        try {
          const priceRes = await fetch(`/api/live-prices?tickers=${encodeURIComponent(tickers.join(','))}`);
          const priceBody = await priceRes.json();
          if (priceBody.ok && priceBody.prices) {
            let updated = false;
            for (const v of allValuations) {
              const livePrice = priceBody.prices[v.ticker.toUpperCase()];
              if (livePrice && livePrice !== v.currentPrice) {
                v.currentPrice = livePrice;
                updated = true;
              }
            }
            if (updated) {
              renderTable(); // Re-render with live prices and updated diffs
            }
          }
        } catch (e) {
          console.error("Failed to fetch live prices", e);
        }
      }
    }
  } catch (err) {
    console.error('Failed to fetch valuations', err);
  }
}

filterInput.addEventListener('input', renderTable);
evaluatorFilter.addEventListener('change', renderTable);

table.querySelectorAll('th').forEach(th => {
  th.addEventListener('click', () => {
    const col = th.getAttribute('data-sort');
    if (!col) return;
    if (sortCol === col) {
      sortAsc = !sortAsc;
    } else {
      sortCol = col;
      sortAsc = true;
    }
    renderTable();
  });
});

fetchValuations();
