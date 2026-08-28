#!/bin/bash
# PreToolUse guard for Bash: blocks shell commands that would WRITE to a protected path.
# Without this, protect-files.sh is only advice — `echo x > .env` bypasses it entirely.
#
# This is a heuristic, not a shell parser: it looks for a protected name used as a word
# together with a write-shaped operation. It errs toward blocking, and the block message
# tells Claude to ask the user, so a false positive costs one question.
# Reads (`cat .env`, `grep KEY .env`) are deliberately NOT blocked.

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=protected-paths.sh
source "$HOOK_DIR/protected-paths.sh"


INPUT=$(cat)   # always drain stdin, even on the early exit below

# Fail CLOSED — see the note in protect-files.sh.
if ! command -v jq >/dev/null 2>&1; then
  echo "Blocked: the protected-paths guard cannot run because 'jq' is not installed, so no file is protected right now. Install jq, or remove this hook from .claude/settings.json to accept the risk deliberately." >&2
  exit 2
fi
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
[ -z "$CMD" ] && exit 0

# Drop fd redirections (2>&1, >&2) so they don't read as writes.
CMD_CLEAN=$(echo "$CMD" | sed -E 's/[0-9]?>&[0-9]//g')

WRITE_OPS='(>|\btee\b|\bsed\b[^|;]*-i|\brm\b|\bmv\b|\bcp\b|\btruncate\b|\bdd\b|\bshred\b|\bchmod\b|\bchown\b|\bln\b|\bgit\b[[:space:]]+\bcheckout\b)'
echo "$CMD_CLEAN" | grep -qE "$WRITE_OPS" || exit 0

# A protected name used as a word: preceded/followed by whitespace, quote, /, = or a
# shell metacharacter — so `out.env.txt` and `myenv` do not match `.env`. Redirect
# operators (`>`/`<`) are included on both sides: `echo x >.env` has no space before the
# name, and without `>` in the boundary class that write slips past unmatched.
mentions() {
  local needle escaped
  needle="$1"
  escaped=$(printf '%s' "$needle" | sed -E 's/[.[\*^$()+?{}|\\]/\\&/g')
  echo "$CMD_CLEAN" | grep -qE "(^|[[:space:]\"'\`/=(;&|<>])${escaped}($|[[:space:]\"'\`;&|)<>])"
}

for name in "${PROTECTED_BASENAMES[@]}"; do
  if mentions "$name"; then
    echo "Blocked: this command writes to '$name', a protected file (secrets or a generated lockfile). Ask the user before running it." >&2
    exit 2
  fi
done

for dir in "${PROTECTED_DIRS[@]}"; do
  if mentions "$dir" || mentions "$dir/"; then
    echo "Blocked: this command writes inside '$dir/', a protected directory. Ask the user before running it." >&2
    exit 2
  fi
done

exit 0
