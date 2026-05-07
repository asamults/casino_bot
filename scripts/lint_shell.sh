#!/usr/bin/env bash
# lint_shell.sh — repo shell-script lint gate (M5W3).
#
# Stages:
#   1) bash -n           : syntax check (always).
#   2) shellcheck        : static analysis (if installed; or REQUIRE_SHELLCHECK=1).
#
# Usage:
#   scripts/lint_shell.sh                  # lint all scripts/**/*.sh
#   scripts/lint_shell.sh path/to/x.sh ... # lint specific files
#   REQUIRE_SHELLCHECK=1 scripts/lint_shell.sh  # fail if shellcheck missing (CI)
#   SHELLCHECK_SEVERITY=warning scripts/lint_shell.sh  # default
#   SHELLCHECK_SEVERITY=style   scripts/lint_shell.sh
#
# Notes:
#   - We deliberately set --severity=warning by default. The point of this
#     gate is "no broken syntax, no real bugs", not full style enforcement.
#   - SC1091 ("source not followed") is excluded because we use dynamic
#     `source "$(dirname ...)/_common.sh"` patterns in scripts/drill/*.

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SHELLCHECK_SEVERITY="${SHELLCHECK_SEVERITY:-warning}"
REQUIRE_SHELLCHECK="${REQUIRE_SHELLCHECK:-0}"
SHELLCHECK_EXCLUDE="${SHELLCHECK_EXCLUDE:-SC1091}"

if [[ "$#" -gt 0 ]]; then
  files=("$@")
else
  mapfile -t files < <(find scripts -type f -name '*.sh' | sort)
fi

if [[ "${#files[@]}" -eq 0 ]]; then
  echo "lint_shell: no shell scripts found under scripts/."
  exit 0
fi

echo "== bash -n (syntax) =="
fail=0
for f in "${files[@]}"; do
  if bash -n "$f"; then
    printf '  ok      %s\n' "$f"
  else
    printf '  FAIL    %s\n' "$f" >&2
    fail=1
  fi
done
if [[ "$fail" -ne 0 ]]; then
  echo "lint_shell: bash -n failed on one or more scripts" >&2
  exit 2
fi

echo
if command -v shellcheck >/dev/null 2>&1; then
  echo "== shellcheck (severity=${SHELLCHECK_SEVERITY}, exclude=${SHELLCHECK_EXCLUDE}) =="
  shellcheck \
    --severity="$SHELLCHECK_SEVERITY" \
    --exclude="$SHELLCHECK_EXCLUDE" \
    --shell=bash \
    -x \
    "${files[@]}"
  echo "shellcheck: clean"
else
  if [[ "$REQUIRE_SHELLCHECK" == "1" ]]; then
    echo "FAIL: shellcheck not installed and REQUIRE_SHELLCHECK=1." >&2
    echo "      install: apt-get install -y shellcheck   (or)   brew install shellcheck" >&2
    exit 3
  fi
  echo "(skipped) shellcheck not installed; bash -n only."
  echo "  install: apt-get install -y shellcheck   (or)   brew install shellcheck"
fi

echo
echo "PASS: shell lint"
