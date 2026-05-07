## Off-host encrypted backup + isolated restore (M5W2)

Scope: take what M5W1 proved (compose `pg_dump`/`pg_restore` rehearsal on the
same volume) and harden the operational model:

1. Backups are **encrypted at rest** (age preferred, gpg supported).
2. Backups are **copied off-host** with a verified checksum.
3. Restore happens in an **isolated compose stack** that does not touch the
   running prod project (separate `COMPOSE_PROJECT_NAME`, separate volumes
   and networks, separate compose file).
4. The whole pipeline is repeatable via `make` targets and produces a
   PASS/FAIL outcome with measured RPO/RTO.

This stage explicitly **does not** cover WAL/PITR. RPO is bounded by how
often you take a backup; RTO is bounded by decrypt + restore + readiness.

---

### Components

- `scripts/ops/pg_backup_encrypt.sh`   — pg_dump → encrypt → sha256 → meta.json
- `scripts/ops/backup_offhost_copy.sh` — copy `.age`/`.gpg` + sidecars to DEST
- `scripts/ops/restore_isolated_compose.sh` — decrypt → isolated stack → pg_restore → probes
- `scripts/ops/rehearsal_offhost_full.sh` — one-shot local DEST: dump → encrypt → copy → restore → probes
- `docker-compose.restore.yml` — restore stack (no fixed `container_name`,
  project-namespaced volumes/networks)
- `.env.restore.example` — env file for the restore stack
- `ops/backup/age-recipients.txt.example` — example recipients file (public keys are safe to commit)

### One-time setup

1. Install `age` on the workstation that will produce/consume backups
   (https://age-encryption.org/). On Debian/Ubuntu:

   ```bash
   sudo apt-get install -y age
   ```

   If you can only use `gpg`, that path is supported too — see the gpg
   section below.

2. Generate an identity (private key) **outside the repo**:

   ```bash
   mkdir -p "$HOME/.config/casino_bot"
   age-keygen -o "$HOME/.config/casino_bot/age-identity.txt"
   chmod 600 "$HOME/.config/casino_bot/age-identity.txt"
   ```

   The `Public key:` line printed by `age-keygen` (starts with `age1...`)
   is what goes into the recipients file.

3. Create the recipients file (public keys; SAFE to commit):

   ```bash
   cp ops/backup/age-recipients.txt.example ops/backup/age-recipients.txt
   # replace the placeholder with the public key from step 2
   ```

4. Copy the restore env file and edit if needed:

   ```bash
   cp .env.restore.example .env.restore
   ```

   `.env.restore` is gitignored. The example file uses the same demo secrets
   as `.env.prod.example` — replace before any non-local use.

### One-command rehearsal (local off-host mock)

End-to-end in one invocation: **backup → encrypt → copy to a second local
path → isolated restore stack → `/health` / `/ready` / `/metrics` probes**
(PASS exits 0, FAIL exits non-zero).

```bash
make rehearsal-offhost BACKUP_DEST=/var/tmp/casino_bot_offhost/ \
  AGE_IDENTITY_FILE="$HOME/.config/casino_bot/age-identity.txt"
```

Optional Make variables: `ENV_FILE` (source dump, default `.env.prod.example`),
`COMPOSE_FILE`, `RESTORE_ENV_FILE` (restore stack, default `.env.restore.example`),
`HOST_HEADER`, `KEEP_STACK=true` (leave the isolated project up for inspection).

Implementation: `scripts/ops/rehearsal_offhost_full.sh`. **SSH-style
`BACKUP_DEST` (`user@host:/path`) is not supported** in this orchestrator,
because `restore_isolated_compose.sh` must read a local `BACKUP_FILE`. For
real off-host destinations, run `make backup-offhost` (or the shell scripts),
then copy or `scp` the artifact back to the restore host and
`make restore-isolated BACKUP_FILE=...`.

### Backup + encrypt (on the host that has access to the prod compose project)

```bash
ENV_FILE=.env.prod.example \
COMPOSE_FILE=docker-compose.prod.yml \
BACKUP_ENCRYPT_TOOL=age \
AGE_RECIPIENTS_FILE=ops/backup/age-recipients.txt \
  ./scripts/ops/pg_backup_encrypt.sh
```

Expected outputs in `./backups/`:

- `casino_bot_<UTC>.dump.age`
- `casino_bot_<UTC>.dump.age.sha256`
- `casino_bot_<UTC>.dump.age.meta.json`

The plaintext `.dump` is removed by default (`KEEP_PLAINTEXT=true` to keep it).

### Off-host copy

Local mock destination (another directory on the same machine — useful for
dry runs / CI):

```bash
BACKUP_FILE=./backups/casino_bot_<UTC>.dump.age \
BACKUP_DEST=/var/tmp/casino_bot_offhost/ \
  ./scripts/ops/backup_offhost_copy.sh
```

Real off-host destination over SSH:

```bash
BACKUP_FILE=./backups/casino_bot_<UTC>.dump.age \
BACKUP_DEST=backupuser@backup.example.com:/var/backups/casino_bot/ \
SSH_OPTS="-i $HOME/.ssh/casino_bot_backup_id_ed25519" \
  ./scripts/ops/backup_offhost_copy.sh
```

The script copies the encrypted blob plus its `.sha256` and `.meta.json`
sidecars, then re-verifies the checksum at the destination. Failure to
verify exits non-zero.

> Never commit `SSH_OPTS`, key paths, or destination credentials. Use a
> local `.env.offhost` (gitignored) if you want to persist these settings.

### Restore in an isolated stack

```bash
BACKUP_FILE=/var/tmp/casino_bot_offhost/casino_bot_<UTC>.dump.age \
AGE_IDENTITY_FILE="$HOME/.config/casino_bot/age-identity.txt" \
ENV_FILE=.env.restore \
HOST_HEADER=api.example.com \
  ./scripts/ops/restore_isolated_compose.sh
```

What the script does:

1. Verifies the `.sha256` sidecar (if present).
2. Decrypts to a temp file in `$(mktemp -d)`; the temp dir is shredded
   on exit.
3. Brings up an isolated compose stack:
   - `COMPOSE_PROJECT_NAME=casino_bot_restore_<UTC timestamp>`
   - `-f docker-compose.restore.yml`
   - container names auto-generated as `<project>-postgres-1`, `<project>-api-1`
   - volume `pgdata` is namespaced to the project (independent from prod)
4. Waits for postgres healthcheck, runs `pg_restore --clean --if-exists`.
5. Starts the isolated `api`, then runs `scripts/ops/pg_verify_compose.sh`
   against the isolated container ID with `HOST_HEADER`.
6. Tears the isolated stack down (set `KEEP_STACK=true` to keep it for
   inspection).

PASS criteria:

- decryption ok, sha256 matches
- isolated postgres healthy
- `pg_restore` returns 0
- `/health`, `/ready`, `/metrics` all 200 from inside the isolated api container

FAIL criteria: any of the above missing.

### gpg variant (optional)

```bash
BACKUP_ENCRYPT_TOOL=gpg \
GPG_RECIPIENT=ops@example.com \
  ./scripts/ops/pg_backup_encrypt.sh

BACKUP_FILE=./backups/casino_bot_<UTC>.dump.gpg \
GPG_PASSPHRASE_FILE=/secure/path/passphrase.txt \
  ./scripts/ops/restore_isolated_compose.sh
```

The passphrase file is gitignored by pattern (`*.gpg.passphrase`); store
it outside the repo for production use.

### RPO / RTO at this stage

- **RPO** ≈ time since last successful `pg_backup_encrypt` + off-host copy.
  No WAL/PITR yet, so any writes after the last backup are lost on disaster.
- **RTO** = time to: pull the encrypted blob from off-host + decrypt +
  bring up isolated stack + `pg_restore` + readiness probe.
  Record actual numbers in
  `docs/ops/offhost-backup-dry-run-report-template.md`.

### Hard rules

- Never commit:
  - private age identities (`age-identity*`, `*.age.key`)
  - gpg passphrases (`*.gpg.passphrase`)
  - SSH keys or off-host credentials (`.env.offhost`)
  - plaintext `.dump` files (`backups/` is gitignored)
- The restore script never touches the prod compose project. If you ever
  see a restore script run with `-f docker-compose.prod.yml`, that is a
  bug — open an incident and stop.

### Cleanup

If `KEEP_STACK=true` was set, clean up the isolated stack later:

```bash
docker compose -p casino_bot_restore_<UTC> -f docker-compose.restore.yml down -v
```

`down -v` removes the per-project `pgdata` volume, which is what we want
for a one-shot restore rehearsal.
