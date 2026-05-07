#!/usr/bin/env bash
# backup_offhost_copy.sh -- copy an encrypted backup + sidecars to an off-host destination.
#
# Inputs:
#   BACKUP_FILE   (required) absolute or relative path to the encrypted backup,
#                 e.g. backups/casino_bot_*.dump.age
#   BACKUP_DEST   (required) destination, one of:
#                   - local directory:           /var/backups/casino_bot/
#                   - remote ssh path:           user@host:/var/backups/casino_bot/
#
# Optional:
#   SSH_OPTS      extra ssh options for scp (e.g. "-i ~/.ssh/backup_id_ed25519")
#   COPY_TOOL     auto|rsync|scp|cp             (default: auto)
#   VERIFY        true|false                    (default: true)
#
# Behavior:
#   - copies BACKUP_FILE plus its .sha256 and .meta.json sidecars (if present)
#   - re-verifies the sha256 at DEST (locally; for remote DEST verifies via ssh)
#   - never logs SSH_OPTS contents
#
# Exit codes:
#   0 ok
#   2 bad input
#   3 copy / verify failure

set -Eeuo pipefail

BACKUP_FILE="${BACKUP_FILE:?BACKUP_FILE is required (path to .dump.age|.dump.gpg)}"
BACKUP_DEST="${BACKUP_DEST:?BACKUP_DEST is required (local dir or user@host:/path/)}"
COPY_TOOL="${COPY_TOOL:-auto}"
VERIFY="${VERIFY:-true}"
SSH_OPTS="${SSH_OPTS:-}"

if [[ ! -s "$BACKUP_FILE" ]]; then
  echo "FAIL: BACKUP_FILE not found or empty: $BACKUP_FILE" >&2
  exit 2
fi

SRC_DIR="$(cd "$(dirname "$BACKUP_FILE")" && pwd)"
SRC_BASE="$(basename "$BACKUP_FILE")"
SRC_FULL="$SRC_DIR/$SRC_BASE"
SHA_FILE="${SRC_FULL}.sha256"
META_FILE="${SRC_FULL}.meta.json"

if [[ ! -s "$SHA_FILE" ]]; then
  echo "FAIL: missing sidecar checksum: $SHA_FILE" >&2
  echo "      run scripts/ops/pg_backup_encrypt.sh first." >&2
  exit 2
fi

echo "== backup_offhost_copy =="
echo "Src:  $SRC_FULL"
echo "Dest: $BACKUP_DEST"

# detect remote vs local
IS_REMOTE=false
if [[ "$BACKUP_DEST" == *":"* && "$BACKUP_DEST" != /* ]]; then
  IS_REMOTE=true
fi

# pick copy tool
pick_tool() {
  local tool="$1"
  if [[ "$tool" == "auto" ]]; then
    if $IS_REMOTE; then
      if command -v rsync >/dev/null 2>&1; then echo rsync; else echo scp; fi
    else
      if command -v rsync >/dev/null 2>&1; then echo rsync; else echo cp; fi
    fi
  else
    echo "$tool"
  fi
}
TOOL="$(pick_tool "$COPY_TOOL")"
echo "Tool: $TOOL"

# ensure remote/local destination dir exists
ensure_dest_dir() {
  if $IS_REMOTE; then
    local host_part path_part qpath
    host_part="${BACKUP_DEST%%:*}"
    path_part="${BACKUP_DEST#*:}"
    # Normalize: treat dest as a directory (rsync/scp expect parent to exist).
    [[ "$path_part" == */ ]] || path_part="${path_part}/"
    qpath="$(printf '%q' "$path_part")"
    # shellcheck disable=SC2086
    ssh $SSH_OPTS "$host_part" "mkdir -p $qpath"
  else
    mkdir -p "$BACKUP_DEST"
  fi
}
ensure_dest_dir

# perform copy of <file>, <file>.sha256, <file>.meta.json
copy_one() {
  local src="$1"
  case "$TOOL" in
    rsync)
      # shellcheck disable=SC2086
      if $IS_REMOTE; then
        rsync -av -e "ssh $SSH_OPTS" "$src" "$BACKUP_DEST"
      else
        rsync -av "$src" "$BACKUP_DEST"
      fi
      ;;
    scp)
      # shellcheck disable=SC2086
      scp $SSH_OPTS "$src" "$BACKUP_DEST"
      ;;
    cp)
      cp -av "$src" "$BACKUP_DEST"
      ;;
    *)
      echo "FAIL: unknown COPY_TOOL=$TOOL" >&2
      exit 2
      ;;
  esac
}

copy_one "$SRC_FULL"
copy_one "$SHA_FILE"
[[ -s "$META_FILE" ]] && copy_one "$META_FILE" || true

# verify checksum at DEST
if [[ "$VERIFY" == "true" ]]; then
  echo "-- verify checksum at DEST --"
  if $IS_REMOTE; then
    host_part="${BACKUP_DEST%%:*}"
    path_part="${BACKUP_DEST#*:}"
    [[ "$path_part" == */ ]] || path_part="${path_part}/"
    # shellcheck disable=SC2086
    ssh $SSH_OPTS "$host_part" \
      "cd '${path_part}' && sha256sum -c '$(basename "$SHA_FILE")'"
  else
    ( cd "$BACKUP_DEST" && sha256sum -c "$(basename "$SHA_FILE")" )
  fi
  echo "PASS: checksum verified at DEST"
else
  echo "(skipped) verify"
fi

echo "OK: off-host copy complete"
