#!/bin/bash
# PostToolUse: format and lint the edited file. Fill in the commands for your stack;
# while they are empty this hook is a no-op, so the kit is safe to copy as-is.
# Examples: FORMAT_CMD="npx prettier --write"  LINT_CMD="npx eslint --max-warnings 0"
#           FORMAT_CMD="ruff format"           LINT_CMD="ruff check"

FORMAT_CMD="$CLAUDE_PROJECT_DIR/.venv/bin/ruff format"
LINT_CMD="$CLAUDE_PROJECT_DIR/.venv/bin/ruff check"

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
[ -z "$FILE_PATH" ] || [ ! -f "$FILE_PATH" ] && exit 0
[[ "$FILE_PATH" != *.py ]] && exit 0

[ -n "$FORMAT_CMD" ] && $FORMAT_CMD "$FILE_PATH"

if [ -n "$LINT_CMD" ]; then
  if ! LINT_OUTPUT=$($LINT_CMD "$FILE_PATH" 2>&1); then
    # Exit 2 feeds lint errors back to Claude so it fixes them immediately.
    echo "$LINT_OUTPUT" | tail -30 >&2
    exit 2
  fi
fi

exit 0
