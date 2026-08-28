#!/bin/bash
# PreToolUse guard for file-editing tools: blocks writes to protected paths.
# exit 2 = block, stderr = the reason, fed back to Claude so it can adjust.
#
# The path list lives in protected-paths.sh — edit it there, not here.
# Shell writes (`echo x > .env`, `sed -i`, `rm`) are covered by protect-bash.sh;
# this guard alone is bypassable, so both must be wired in settings.json.

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=protected-paths.sh
source "$HOOK_DIR/protected-paths.sh"


INPUT=$(cat)   # always drain stdin, even on the early exit below

# Fail CLOSED. Without jq this hook cannot read the event, and exiting 0 would leave the
# repo unguarded while still looking installed — the worst outcome for a guard.
if ! command -v jq >/dev/null 2>&1; then
  echo "Blocked: the protected-paths guard cannot run because 'jq' is not installed, so no file is protected right now. Install jq, or remove this hook from .claude/settings.json to accept the risk deliberately." >&2
  exit 2
fi
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty')

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

if is_protected "$FILE_PATH"; then
  echo "Blocked: $FILE_PATH — $REASON. Ask the user before touching this file." >&2
  exit 2
fi

exit 0
