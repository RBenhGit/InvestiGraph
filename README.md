# Eps_Evaluation

An EPS×multiple stock valuation tool. It fetches fundamentals from the Twelve Data API and analyst consensus from Yahoo Finance, and computes two independent "fair value" estimates:
- Peter Lynch style (PEG ratio, no discounting)
- Rule #1 style (EPS projection × exit multiple, discounted)

The tool is available via both a CLI and a Web interface.

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
npm run cli -- AAPL
```

### Web UI

Start the local Fastify server to view the valuations with an interactive UI. The web UI additionally provides analyst consensus data from Yahoo Finance.

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
