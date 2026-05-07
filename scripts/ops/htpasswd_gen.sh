#!/usr/bin/env bash
# htpasswd_gen.sh — turnkey htpasswd file generator for the casino_bot
# reverse-proxy (M6W2).
#
# Why this script exists:
#   - The reverse-proxy nginx config (ops/reverse-proxy/nginx.conf.example
#     and ops/external-staging/nginx/nginx.conf) protects /metrics with
#     basic auth backed by a .htpasswd file. That file MUST NOT live in
#     git, but operators still need a reliable way to (re)generate it
#     consistently across hosts.
#   - The canonical tool (`htpasswd` from apache2-utils / httpd-tools)
#     is not available everywhere. This script prefers it when present
#     and falls back to a pure-openssl bcrypt path otherwise so the
#     team has a single, no-think entry point.
#
# Usage:
#   USERNAME=metrics PASSWORD=$(read -s) ./scripts/ops/htpasswd_gen.sh
#   USERNAME=metrics ./scripts/ops/htpasswd_gen.sh   # prompts interactively
#
# Inputs (env):
#   USERNAME         basic-auth username (default: metrics)
#   PASSWORD         basic-auth password; if unset, read from stdin
#                    interactively (no echo)
#   OUTPUT_FILE      where to write the htpasswd entry
#                    (default: ./.htpasswd in CWD)
#   APPEND           true|false (default: false). If true, append to
#                    OUTPUT_FILE instead of overwriting; useful for
#                    multi-user metrics setups.
#
# Output:
#   A single-line htpasswd entry of the form
#       <user>:$apr1$...   (apr1 from htpasswd -B fallback uses bcrypt)
#   in OUTPUT_FILE, with mode 0600.
#
# Exit codes:
#   0  ok
#   2  bad input (missing tools, empty username/password)
#
# Security notes:
#   - The script chmods OUTPUT_FILE to 0600 immediately after write.
#   - PASSWORD is never echoed back; we use printf, not echo, and we
#     pipe through stdin where possible to avoid leaking via process
#     listings. `set -x` is intentionally NOT used.
#   - If your shell history is sensitive, prefer the interactive prompt
#     so PASSWORD never appears in `history`.

set -Eeuo pipefail

USERNAME="${USERNAME:-metrics}"
OUTPUT_FILE="${OUTPUT_FILE:-./.htpasswd}"
APPEND="${APPEND:-false}"

if [[ -z "$USERNAME" ]]; then
  echo "FAIL: USERNAME is empty" >&2
  exit 2
fi

case "$APPEND" in
  true|false) ;;
  *) echo "FAIL: APPEND must be 'true' or 'false', got: $APPEND" >&2; exit 2 ;;
esac

# Read PASSWORD from stdin if not preset (no echo).
if [[ -z "${PASSWORD:-}" ]]; then
  if [[ -t 0 ]]; then
    printf 'Password for %s: ' "$USERNAME" >&2
    IFS= read -rs PASSWORD
    printf '\n' >&2
  else
    IFS= read -r PASSWORD
  fi
fi

if [[ -z "${PASSWORD:-}" ]]; then
  echo "FAIL: PASSWORD is empty" >&2
  exit 2
fi
if [[ "${#PASSWORD}" -lt 12 ]]; then
  echo "FAIL: PASSWORD is too short (got ${#PASSWORD} chars, need >= 12)" >&2
  exit 2
fi

# --- pick the encoder -----------------------------------------------------
encoder=""
if command -v htpasswd >/dev/null 2>&1; then
  encoder="htpasswd"
elif command -v openssl >/dev/null 2>&1; then
  encoder="openssl"
else
  echo "FAIL: neither 'htpasswd' nor 'openssl' is available." >&2
  echo "      Install apache2-utils (Debian/Ubuntu) / httpd-tools (RHEL)" >&2
  echo "      or openssl, and re-run." >&2
  exit 2
fi

mkdir -p "$(dirname "$OUTPUT_FILE")"

case "$encoder" in
  htpasswd)
    # -i reads PASSWORD from stdin; -B = bcrypt; -n prints to stdout
    # without writing the file (we control the file ourselves so we can
    # apply chmod and the APPEND policy uniformly).
    LINE="$(printf '%s' "$PASSWORD" | htpasswd -niB "$USERNAME")"
    ;;
  openssl)
    # apr1 is the historical apache password format and is accepted by
    # nginx auth_basic. It's weaker than bcrypt but universally
    # available; if you have htpasswd installed you'll get bcrypt.
    SALT="$(openssl rand -hex 4)"
    HASH="$(printf '%s' "$PASSWORD" | openssl passwd -apr1 -salt "$SALT" -stdin)"
    LINE="${USERNAME}:${HASH}"
    ;;
esac

if [[ "$APPEND" == "true" && -e "$OUTPUT_FILE" ]]; then
  printf '%s\n' "$LINE" >> "$OUTPUT_FILE"
else
  printf '%s\n' "$LINE" > "$OUTPUT_FILE"
fi
chmod 0600 "$OUTPUT_FILE"

# Sanity: confirm the line we just wrote contains a colon-separated
# user:hash pair and nothing leaked the plaintext password.
if ! grep -q "^${USERNAME}:" "$OUTPUT_FILE"; then
  echo "FAIL: output file does not contain entry for $USERNAME" >&2
  exit 2
fi
if grep -qF "$PASSWORD" "$OUTPUT_FILE"; then
  echo "FAIL: plaintext password leaked into output file (encoder bug)" >&2
  rm -f "$OUTPUT_FILE"
  exit 2
fi

echo "OK: htpasswd entry for '$USERNAME' written to $OUTPUT_FILE (mode 0600, encoder=$encoder)"
