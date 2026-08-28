# Eps_Evaluation

An EPS×multiple stock valuation tool. It fetches fundamentals from the Twelve Data API and analyst consensus from Yahoo Finance, and computes two independent "fair value" estimates:
- Peter Lynch style (PEG ratio, no discounting)
- Rule #1 style (EPS projection × exit multiple, discounted)

The tool is available via both a CLI and a Web interface, and supports saving valuations and tracking historical estimates over time.

## Prerequisites

- Node.js 18 or higher
- A [Twelve Data API key](https://twelvedata.com/) (free tier is supported, but some growth metrics may gracefully degrade to `null` on non-Enterprise plans).

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd Eps_Evaluation

# Install dependencies
npm install

# Setup environment variables
cp .env.example .env
# Edit .env and insert your TWELVE_DATA_API_KEY
```

## Usage

### CLI

Run the valuation logic directly in your terminal for a given stock ticker:

```bash
# Calculate valuation
npm run cli -- AAPL

# Calculate valuation and save to history
npm run cli -- AAPL --save

# Apply a Margin of Safety to Rule #1's fair value (e.g. 25 for 25%)
npm run cli -- AAPL --mos 25

# Save with a note/investment thesis attached
npm run cli -- AAPL --save --notes "Strong data-center demand"

# View all saved historical valuations
npm run cli -- --history

# View history filtered by ticker
npm run cli -- --history AAPL
```

Flags: `-s, --save` (save the result to history), `-m, --mos <percent>` (Margin of Safety for
Rule #1, default `0`), `-n, --notes <text>` (thesis attached to a saved valuation),
`-H, --history [ticker]` (print saved valuations, optionally filtered by ticker).

### Web UI

Start the local Fastify server to view the valuations with an interactive UI. The web UI additionally provides analyst consensus data from Yahoo Finance, and allows saving valuations and managing history directly from the browser:

```bash
npm run web
```
The server will start on port `3210` by default (configurable via `PORT` in `.env`). Open `http://localhost:3210` in your browser.

The server binds to `127.0.0.1` only, so it is not reachable from other machines on your network. The app has no authentication of its own; if you need remote access, put an authenticated proxy (e.g. Tailscale Serve) in front of it rather than widening the bind address.

The web UI offers two things the CLI does not:

- **Bear / Base / Bull scenarios** — every valuation computes all three at once, each with its own editable growth rate, exit P/E, and required return. Margin of Safety is a single value shared across all three.
- **Evaluator** — a dropdown naming who performed the valuation, saved onto the record. The list of names is managed in the picker itself and is stored per-browser; the chosen name is saved with the valuation. The CLI has no equivalent, so CLI-saved valuations simply show as unowned.

### All Valuations page

The web UI also has an **All Valuations** dashboard, linked from the header (or open `http://localhost:3210/valuations.html` directly). It shows the most recent saved valuation per ticker **per evaluator**, using the base scenario only:

- Sortable columns (date, ticker, current price, both fair values, both upside percentages, evaluator)
- A ticker text filter and an evaluator dropdown filter
- Live price refresh, so the upside percentages reflect the current market price rather than the price captured when the valuation was saved
- A bar chart of Rule #1 upside % for valuations from the last six months

This page renders its chart with [Chart.js](https://www.chartjs.org/), loaded from a CDN at a pinned version rather than installed via npm — so it needs network access on first load, and the chart (only) will be missing if you open the page offline.

## Development

- **Build**: `npm run build`
- **Test**: `npm test`
- **Lint**: `npm run lint`
- **Format**: `npm run format`

Running the test suite requires **Node 20.12 or newer** (vitest's bundler needs `node:util`'s `styleText`), even though the app itself runs on Node 18.

For more details on the architecture and codebase rules, refer to `CLAUDE.md`.
