#!/usr/bin/env bash
# secrets_hygiene_check.sh — fail closed if the working tree contains
# any forbidden artifact (M6W2).
#
# This is a *path-level* check, not a content scanner. The principle is
# simple: certain file shapes should never be committed. If git doesn't
# ignore them and they exist on disk, either:
#   (a) someone is about to accidentally commit a secret/binary, or
#   (b) .gitignore drifted away from reality.
#
# Forbidden patterns (any tracked-or-untracked match fails):
#   - backups/                       (encrypted dumps + sidecars)
#   - artifacts/                     (drill reports / evidence)
#   - *.dump / *.dump.age / *.dump.gpg
#   - .env, .env.prod, .env.staging, .env.offhost, .env.restore
#   - *.htpasswd
#   - **/tls/*.key, *.pem, *.crt     (proxy TLS material)
#   - **/age-identity*, **/*.age.key, **/*.gpg.passphrase
#
# How "tracked-or-untracked" is decided:
#   - In a git checkout we use `git ls-files -coz --exclude-standard`
#     plus `git ls-files -z` so we catch BOTH "untracked but not
#     ignored" files (the dangerous case) AND files that ARE tracked
#     when they shouldn't be (regression catch).
#   - Outside git we fall back to `find`, which is fine for ad-hoc
#     local runs but not used in CI.
#
# Inputs (env):
#   ROOT       repo root (default: pwd)
#   IGNORE     comma-separated extra path globs to ignore (rare; document
#              every entry inline).
#
# Exit codes:
#   0  clean
#   2  bad input or required tool missing
#   3  one or more forbidden paths found

set -Eeuo pipefail

ROOT="${ROOT:-$(pwd)}"
IGNORE="${IGNORE:-}"

cd "$ROOT"

echo "== secrets_hygiene_check =="
echo "Root: $ROOT"

# Forbidden glob patterns. Each entry is a Bash-style glob applied
# relative to the repo root. Update this list together with
# docs/ops/secrets-hygiene.md so the docs and the gate stay in sync.
FORBIDDEN_PATTERNS=(
  'backups/'
  'artifacts/'
  '*.dump'
  '*.dump.age'
  '*.dump.gpg'
  '.env'
  '.env.prod'
  '.env.staging'
  '.env.offhost'
  '.env.restore'
  '*.htpasswd'
  '**/tls/*.key'
  '**/tls/*.pem'
  '**/tls/*.crt'
  '**/age-identity*'
  '**/*.age.key'
  '**/*.gpg.passphrase'
)

# Honor an inline IGNORE list. We keep this conservative: the only
# legitimate use is to whitelist *example* files (e.g. .env.example) if
# a future pattern accidentally matches them.
declare -A IGNORE_SET=()
if [[ -n "$IGNORE" ]]; then
  IFS=',' read -ra _ignored <<< "$IGNORE"
  for entry in "${_ignored[@]}"; do
    entry="${entry## }"; entry="${entry%% }"
    [[ -z "$entry" ]] && continue
    IGNORE_SET["$entry"]=1
  done
fi

# Build the list of candidate paths. In a git repo we want both
# tracked AND untracked-but-not-ignored files; that's the union of
# what could *be* committed.
list_candidates() {
  if [[ -d .git ]] && command -v git >/dev/null 2>&1; then
    {
      git ls-files -z
      git ls-files -coz --exclude-standard
    } | tr '\0' '\n' | sort -u
  else
    # Outside git: every file under root, minus the obvious noise.
    find . \
      -path ./.git -prune -o \
      -path ./.venv -prune -o \
      -path ./.pytest_cache -prune -o \
      -path ./node_modules -prune -o \
      -type f -print | sed 's|^\./||' | sort -u
  fi
}

# Match a path against a glob using Bash's `[[ == ]]` (extended
# globbing). globstar is required for `**` patterns.
shopt -s globstar nullglob extglob

violations=0
violators=()

while IFS= read -r path; do
  [[ -z "$path" ]] && continue
  # Honor explicit IGNORE entries verbatim.
  if [[ -n "${IGNORE_SET[$path]:-}" ]]; then
    continue
  fi

  for pat in "${FORBIDDEN_PATTERNS[@]}"; do
    # Directory-style patterns (trailing /) match the dir itself or
    # anything under it.
    if [[ "$pat" == */ ]]; then
      stripped="${pat%/}"
      if [[ "$path" == "$stripped" || "$path" == "$stripped"/* ]]; then
        violators+=("$path  (matches $pat)")
        violations=$((violations + 1))
        break
      fi
      continue
    fi

    # File-style patterns. We match against the basename for
    # simple-name patterns (no '/'), or the full path for ** patterns.
    if [[ "$pat" == *"/"* ]]; then
      # shellcheck disable=SC2053 # glob match intended on rhs
      if [[ "$path" == $pat ]]; then
        violators+=("$path  (matches $pat)")
        violations=$((violations + 1))
        break
      fi
    else
      base="${path##*/}"
      # shellcheck disable=SC2053 # glob match intended on rhs
      if [[ "$base" == $pat ]]; then
        violators+=("$path  (matches $pat)")
        violations=$((violations + 1))
        break
      fi
    fi
  done
done < <(list_candidates)

if [[ "$violations" -gt 0 ]]; then
  echo
  echo "FAIL: ${violations} forbidden path(s) found:" >&2
  for v in "${violators[@]}"; do
    echo "  - $v" >&2
  done
  echo
  echo "If a match is a legitimate example/template, either rename it"
  echo "(e.g. .env.example is fine, .env is not) or add it to the IGNORE"
  echo "list with a justification in docs/ops/secrets-hygiene.md." >&2
  exit 3
fi

echo "PASS: no forbidden paths found"
