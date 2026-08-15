#!/bin/bash
# Stop gate: refuses to let the turn end while tests fail. Fill in TEST_CMD for your
# stack; while it is empty this hook is a no-op. Claude Code overrides the gate after
# 8 consecutive blocks, so a genuinely stuck run still terminates.
# Example: TEST_CMD="npm test --silent"   TEST_CMD="pytest -q"
#
# Routed over SSH, not run locally: this project lives on a `Z:` SSHFS mount whose
# Windows driver returns EPERM (not the POSIX-standard EEXIST) on `mkdir` of an
# already-existing directory. That breaks `npm install` from this shell, so
# node_modules here is permanently stuck with the wrong-platform esbuild binary and
# `npx vitest run` can never succeed locally — not a real test failure, a broken
# local environment. The same files are reachable via SSH on the host that actually
# owns the filesystem (native Linux, no mkdir bug, node_modules already correct
# there); running the suite through that SSH hop is what actually verifies the code.
# If that host/path/key ever changes, update the remote cd target below.
TEST_CMD="ssh -o BatchMode=yes -o ConnectTimeout=10 aviv@100.76.172.46 'cd /home/aviv/shared_disk/Cursor_apps/Eps_Evaluation && npm test'"

INPUT=$(cat)   # always drain stdin, even on the early exits below

# No gate configured → no-op, jq or not.
[ -z "$TEST_CMD" ] && exit 0

if ! command -v jq >/dev/null 2>&1; then
  echo "Test gate disabled: 'jq' is not installed, so .claude/hooks/stop-test-gate.sh cannot read the event. Install jq, or clear TEST_CMD. No test ran — do NOT try to fix the code." >&2
  exit 2
fi

# Prevent an infinite loop: if this hook already blocked the previous stop, let it pass.
if [ "$(echo "$INPUT" | jq -r '.stop_hook_active')" = "true" ]; then
  exit 0
fi

# Skip the suite when the repo is byte-for-byte what was verified last time, so
# conversational turns are free. This fingerprints HEAD *and* the working tree — a
# commit moves HEAD, so committed-but-unverified work still triggers a run.
STATE_FILE=""
if GIT_DIR_PATH=$(git rev-parse --git-dir 2>/dev/null); then
  STATE_FILE="$GIT_DIR_PATH/claude-test-gate-state"
  FINGERPRINT=$({
    git rev-parse HEAD 2>/dev/null
    git status --porcelain 2>/dev/null
    git diff HEAD 2>/dev/null
    git ls-files --others --exclude-standard -z 2>/dev/null | xargs -0 -r cat 2>/dev/null
  } | sha1sum | cut -d' ' -f1)

  if [ -f "$STATE_FILE" ] && [ "$(cat "$STATE_FILE")" = "$FINGERPRINT" ]; then
    exit 0
  fi
fi

TEST_OUTPUT=$(eval "$TEST_CMD" 2>&1)
TEST_STATUS=$?

if [ "$TEST_STATUS" -eq 127 ]; then
  # A missing command is a setup error. Reporting it as a test failure sends Claude
  # chasing failures that do not exist, for up to 8 blocked turns.
  echo "Test gate misconfigured: '${TEST_CMD%% *}' not found. Fix TEST_CMD in .claude/hooks/stop-test-gate.sh (or clear it to disable the gate). Do NOT try to fix the code — no test actually ran." >&2
  exit 2
fi

if [ "$TEST_STATUS" -ne 0 ]; then
  {
    echo "Tests are failing — the task is not done. Fix the failures (root cause, do not skip or weaken tests) and run the suite again:"
    echo "$TEST_OUTPUT" | tail -40
  } >&2
  exit 2
fi

# Record what was verified, so the next turn can skip an identical tree.
[ -n "$STATE_FILE" ] && printf '%s' "$FINGERPRINT" > "$STATE_FILE" 2>/dev/null

exit 0
