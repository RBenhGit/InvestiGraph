#!/bin/bash
# Shared definition of protected paths, sourced by protect-files.sh (Edit|Write) and
# protect-bash.sh (shell writes). One list, so the two guards cannot drift apart.
#
# Matching is on the BASENAME, not a substring: ".env" protects `.env` and `config/.env`
# but not `.env.example` or `client/.env.d.ts`. Substring matching over-blocks, and a guard
# that blocks legitimate files gets deleted rather than tuned.

# Exceptions win over everything else — list files that look protected but are editable.
ALLOWED_BASENAMES=(
  ".env.example" ".env.sample" ".env.template" ".env.d.ts"
)

# Exact basenames that must never be edited by an agent without asking.
PROTECTED_BASENAMES=(
  ".env" ".env.local" ".env.development" ".env.production" ".env.test"
  "package-lock.json" "yarn.lock" "pnpm-lock.yaml" "bun.lockb"
  "Cargo.lock" "poetry.lock" "uv.lock" "Pipfile.lock"
  "go.sum" "Gemfile.lock" "composer.lock"
  "id_rsa" "id_ed25519" ".npmrc" ".pypirc"
)

# Directories that are off limits, matched as a path segment.
PROTECTED_DIRS=(
  ".git"
)

# is_protected <path> -> exit 0 if protected (REASON is set), 1 otherwise.
is_protected() {
  local path="$1" base ok name dir
  REASON=""
  [ -z "$path" ] && return 1
  base="${path##*/}"

  for ok in "${ALLOWED_BASENAMES[@]}"; do
    [ "$base" = "$ok" ] && return 1
  done

  for name in "${PROTECTED_BASENAMES[@]}"; do
    if [ "$base" = "$name" ]; then
      REASON="'$name' is a protected file (secrets or a generated lockfile)"
      return 0
    fi
  done

  for dir in "${PROTECTED_DIRS[@]}"; do
    case "$path" in
      "$dir"/*|*/"$dir"/*)
        REASON="'$dir/' is a protected directory"
        return 0
        ;;
    esac
  done

  return 1
}
