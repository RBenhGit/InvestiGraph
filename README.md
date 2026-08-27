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

## Development

- **Build**: `npm run build`
- **Test**: `npm test`
- **Lint**: `npm run lint`
- **Format**: `npm run format`

For more details on the architecture and codebase rules, refer to `CLAUDE.md`.
