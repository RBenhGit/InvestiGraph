#!/usr/bin/env bash
# Runs the full InvestiGraph suite: Python (pytest) + front-end (vitest).
# Front-end tests require Node >=22.22.2 (jsdom@30's declared engine floor — see
# PROGRESS.md's "Node version" note) — this script resolves an nvm-installed Node 22
# explicitly so it doesn't depend on whatever Node happens to be first on $PATH.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "==> pytest"
uv run pytest -q

REQUIRED_NODE="22.22.2"
version_ge() { # $1 >= $2, both dotted-numeric
    [ "$1" = "$2" ] && return 0
    [ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | head -n1)" = "$2" ]
}

NODE22_BIN="$HOME/.nvm/versions/node/v22.23.2/bin"
if [ -d "$NODE22_BIN" ]; then
    export PATH="$NODE22_BIN:$PATH"
else
    node_version="$(node --version 2>/dev/null | sed 's/^v//')"
    if [ -z "$node_version" ] || ! version_ge "$node_version" "$REQUIRED_NODE"; then
        echo "error: Node >=$REQUIRED_NODE required for front-end tests (jsdom's declared engine floor)." >&2
        echo "       install via nvm: nvm install 22" >&2
        exit 1
    fi
fi

echo "==> vitest"
[ -d node_modules ] || npm install
npx vitest run
