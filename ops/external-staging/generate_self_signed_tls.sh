#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TLS_DIR="$ROOT_DIR/ops/external-staging/nginx/tls"

DOMAIN="${1:-api.example.com}"

mkdir -p "$TLS_DIR"

if [[ -f "$TLS_DIR/tls.crt" && -f "$TLS_DIR/tls.key" ]]; then
  echo "TLS cert already exists at $TLS_DIR (skipping)"
  exit 0
fi

echo "Generating self-signed TLS cert for CN=$DOMAIN"

openssl req -x509 -newkey rsa:2048 -sha256 -days 30 -nodes \
  -keyout "$TLS_DIR/tls.key" \
  -out "$TLS_DIR/tls.crt" \
  -subj "/CN=$DOMAIN" \
  -addext "subjectAltName=DNS:$DOMAIN"

echo "OK: wrote $TLS_DIR/tls.crt and $TLS_DIR/tls.key"

