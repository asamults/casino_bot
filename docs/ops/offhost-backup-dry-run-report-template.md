## Off-host encrypted backup + isolated restore — dry-run report (TEMPLATE)

Date (UTC): YYYY-MM-DDTHH:MM:SSZ
Owner: <name>
Source compose: `docker-compose.prod.yml` (project `casino_bot`)
Restore compose: `docker-compose.restore.yml` (project `casino_bot_restore_<UTC>`)
Env file (source): `.env.prod.example` / `.env.prod`
Env file (restore): `.env.restore.example` / `.env.restore`
Encryption tool: age | gpg
Recipients file (age) / recipient (gpg): <value>

---

### Objective

Prove the M5W2 invariant: an **encrypted** backup, **copied off-host**, can
be **restored into an isolated compose stack** that does not touch the
running prod project, and the app becomes ready again.

---

### One-command path (optional, local mock DEST)

```
make rehearsal-offhost BACKUP_DEST=/var/tmp/casino_bot_offhost/ \
  AGE_IDENTITY_FILE=$HOME/.config/casino_bot/age-identity.txt
```

Use the split steps below if `BACKUP_DEST` is remote SSH or you need separate evidence.

---

### Step 1 — Backup + encrypt

Command (split path — encrypt + copy):

```
make backup-offhost BACKUP_DEST=<dest>
```

Encrypt only (then copy manually):

```
./scripts/ops/pg_backup_encrypt.sh
```

Outputs:

- Encrypted blob: `./backups/<file>.dump.<ext>`
- Checksum:       `./backups/<file>.dump.<ext>.sha256`
- Metadata:       `./backups/<file>.dump.<ext>.meta.json`

Recorded:

- Plaintext size (bytes): <n>
- Encrypted size (bytes): <n>
- sha256: `<hex>`
- Backup wall time (s): <n>

### Step 2 — Off-host copy

Destination: `<local dir | user@host:/path/>`
Tool used: `rsync` | `scp` | `cp`

Outputs at DEST (must include all three):

- `<file>.dump.<ext>`
- `<file>.dump.<ext>.sha256`
- `<file>.dump.<ext>.meta.json`

Verification: `sha256sum -c` at DEST returned: PASS / FAIL
Copy wall time (s): <n>

### Step 3 — Restore into isolated stack

Command:

```
make restore-isolated BACKUP_FILE=<path-at-dest> AGE_IDENTITY_FILE=<path>
```

Project name created: `casino_bot_restore_<UTC>`
Containers seen via `docker ps`:

- `casino_bot_restore_<UTC>-postgres-1`
- `casino_bot_restore_<UTC>-api-1`

Confirmed isolation:

- [ ] no overlap with `casino_bot-postgres` / `casino_bot-api` container names
- [ ] separate volume `casino_bot_restore_<UTC>_pgdata`
- [ ] separate compose network

Decryption: PASS / FAIL
`pg_restore` exit code: <n>
Restore wall time (s): <n>

### Step 4 — Verify probes (isolated api)

Command:

```
make verify-restore-isolated API_CONTAINER=casino_bot_restore_<UTC>-api-1
```

- `/health`:  PASS / FAIL  (status: <n>)
- `/ready`:   PASS / FAIL  (status: <n>)
- `/metrics`: PASS / FAIL  (status: <n>)
Probe wall time (s): <n>

---

### RPO / RTO (measured)

- RPO (interval since previous successful backup): <e.g. 24h, manual>
- RTO_total = decrypt + isolated up + pg_restore + readiness = <s>
  - decrypt:        <s>
  - isolated up:    <s>
  - pg_restore:     <s>
  - readiness:      <s>

Targets at this stage (no WAL/PITR):

- RPO target: ≤ <X> hours (set by backup cadence)
- RTO target: ≤ <Y> minutes (set by op)

### Issues / notes

- <bullets>

### Result

PASS / FAIL

### Cleanup

- Isolated stack torn down: YES / NO (KEEP_STACK=<true|false>)
- Decrypted plaintext shredded: YES (script does this on exit)
- Off-host artifact retained: YES / NO
