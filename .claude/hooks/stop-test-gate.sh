#!/bin/bash
# Stop gate: refuses to let the turn end while tests fail. Fill in TEST_CMD for your
# stack; while it is empty this hook is a no-op. Claude Code overrides the gate after
# 8 consecutive blocks, so a genuinely stuck run still terminates.
# Example: TEST_CMD="npm test --silent"   TEST_CMD="pytest -q"

TEST_CMD="$CLAUDE_PROJECT_DIR/.venv/bin/pytest -q"

INPUT=$(cat)

# Prevent an infinite loop: if this hook already blocked the previous stop, let it pass.
if [ "$(echo "$INPUT" | jq -r '.stop_hook_active')" = "true" ]; then
  exit 0
fi

[ -z "$TEST_CMD" ] && exit 0

if ! TEST_OUTPUT=$($TEST_CMD 2>&1); then
  {
    echo "Tests are failing — the task is not done. Fix the failures (root cause, do not skip or weaken tests) and run the suite again:"
    echo "$TEST_OUTPUT" | tail -40
  } >&2
  exit 2
fi

exit 0
