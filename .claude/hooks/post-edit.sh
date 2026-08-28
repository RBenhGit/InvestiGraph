#!/bin/bash
# PostToolUse: format and lint the edited file. Fill in the commands for your stack;
# while they are empty this hook is a no-op, so the kit is safe to copy as-is.
# Examples: FORMAT_CMD="npx prettier --write"  LINT_CMD="npx eslint --max-warnings 0"
#           FORMAT_CMD="ruff format"           LINT_CMD="ruff check"
#
# LINT_EXTENSIONS matters: a code linter run on a README fails with a parse error and
# blocks the turn. Trim this list to the extensions your linter actually understands.
# Scoped to .py only — the front-end JS under web/static/ is Eps_Evaluation's original
# files kept verbatim (see docs/MERGE_SPEC.md), not linted by this project's own tooling.

FORMAT_CMD="$CLAUDE_PROJECT_DIR/.venv/bin/ruff format"
LINT_CMD="$CLAUDE_PROJECT_DIR/.venv/bin/ruff check"
LINT_EXTENSIONS="py"

INPUT=$(cat)   # always drain stdin, even on the early exits below

# Nothing configured → nothing to do, jq or not. Configured but no jq → say so, don't pretend.
if [ -z "$FORMAT_CMD" ] && [ -z "$LINT_CMD" ]; then
  exit 0
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "Format/lint hook disabled: 'jq' is not installed, so .claude/hooks/post-edit.sh cannot read the event. Install jq, or clear FORMAT_CMD/LINT_CMD. This is a setup problem, not a problem with the file you edited." >&2
  exit 2
fi

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty')

if [ -z "$FILE_PATH" ] || [ ! -f "$FILE_PATH" ]; then
  exit 0
fi

# Format/lint only file types the tools understand (also gates FORMAT_CMD here, since
# ruff format on a non-.py file is as wrong as ruff check on one).
EXT="${FILE_PATH##*.}"
case " $LINT_EXTENSIONS " in
  *" $EXT "*) ;;
  *) exit 0 ;;
esac

if [ -n "$FORMAT_CMD" ]; then
  $FORMAT_CMD "$FILE_PATH" >/dev/null 2>&1
fi

[ -z "$LINT_CMD" ] && exit 0

LINT_OUTPUT=$($LINT_CMD "$FILE_PATH" 2>&1)
LINT_STATUS=$?

if [ "$LINT_STATUS" -eq 127 ]; then
  # Setup error, not a code problem — say so, or Claude will try to fix the file.
  echo "Lint hook misconfigured: '${LINT_CMD%% *}' not found. Fix LINT_CMD in .claude/hooks/post-edit.sh (or clear it). This is a setup problem, not a problem with $FILE_PATH." >&2
  exit 2
fi

if [ "$LINT_STATUS" -ne 0 ]; then
  # exit 2 feeds lint errors back to Claude so it fixes them immediately.
  echo "$LINT_OUTPUT" | tail -30 >&2
  exit 2
fi

exit 0
