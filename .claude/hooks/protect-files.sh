#!/bin/bash
# PreToolUse guard: blocks edits to protected paths (exit 2 = block, stderr = reason).
# Add project-specific patterns below.

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
[ -z "$FILE_PATH" ] && exit 0

PROTECTED_PATTERNS=(".env" ".git/" "package-lock.json" "yarn.lock" "pnpm-lock.yaml")

for pattern in "${PROTECTED_PATTERNS[@]}"; do
  if [[ "$FILE_PATH" == *"$pattern"* ]]; then
    echo "Blocked: $FILE_PATH matches protected pattern '$pattern'. Ask the user before touching this file." >&2
    exit 2
  fi
done

exit 0
