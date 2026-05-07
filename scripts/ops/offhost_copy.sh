#!/usr/bin/env bash
# offhost_copy.sh -- M6W3 contract wrapper for off-host copy + checksum verify.
#
# This script intentionally delegates to the already-audited implementation
# in scripts/ops/backup_offhost_copy.sh, but keeps the M6W3 filename/entrypoint.
#
# Required env:
#   BACKUP_FILE   path to encrypted backup (.dump.age or .dump.gpg)
#   BACKUP_DEST   local dir or user@host:/path/
#
# Optional env:
#   COPY_TOOL, SSH_OPTS, VERIFY (see backup_offhost_copy.sh)
#
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

BACKUP_FILE="${BACKUP_FILE:?BACKUP_FILE is required}"
BACKUP_DEST="${BACKUP_DEST:?BACKUP_DEST is required}"

exec "$ROOT_DIR/scripts/ops/backup_offhost_copy.sh"

