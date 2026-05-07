## Off-host encrypted backup + isolated restore — dry-run report

Date (UTC): 2026-05-07T19:47:00Z
Owner: <fill>
Source compose: `docker-compose.prod.yml` (project `casino_bot`)
Restore compose: `docker-compose.restore.yml` (project `restore_<UTC>`)
Env file (source): `.env.prod.example` / `.env.prod`
Env file (restore): `.env.restore.example` / `.env.restore`
Encryption tool: age
Recipients file (age): `ops/backup/age-recipients.txt`

---

### Objective

Prove that an **encrypted** backup, **copied off-host**, can be **restored from the off-host artifact** into an isolated compose project (`restore_<UTC>`), and the app becomes ready again (`/health`, `/ready`, `/metrics` all 200).

---

### Step 1 — Backup + encrypt

Command:

```
./scripts/ops/pg_backup_encrypt.sh
```

Outputs:

- Encrypted blob: `./backups/casino_bot_<UTC>.dump.age`
- Checksum:       `./backups/casino_bot_<UTC>.dump.age.sha256`
- Metadata:       `./backups/casino_bot_<UTC>.dump.age.meta.json`

Manifest verification:

```
python3 scripts/ops/verify_backup_manifest.py ./backups/casino_bot_<UTC>.dump.age
```

Recorded:

- Backup wall time (s): <fill>
- sha256: `<fill>`

### Step 2 — Off-host copy

Destination: `/var/tmp/casino_bot_offhost/` (local mirror for dry-run)
Tool used: `rsync|cp` (auto)

Command:

```
BACKUP_FILE=./backups/casino_bot_<UTC>.dump.age BACKUP_DEST=/var/tmp/casino_bot_offhost/ \
  ./scripts/ops/offhost_copy.sh
```

Verification: `sha256sum -c` at DEST returned: PASS
Copy wall time (s): <fill>

### Step 3 — Restore into isolated stack (from off-host)

Command:

```
BACKUP_SRC=/var/tmp/casino_bot_offhost/casino_bot_<UTC>.dump.age \
AGE_IDENTITY_FILE=$HOME/.config/casino_bot/age-identity.txt \
ENV_FILE=.env.restore.example \
  ./scripts/ops/restore_offhost_isolated.sh
```

Project name created: `restore_<UTC>`
Decryption: PASS
`pg_restore` exit code: 0
Restore wall time (s): <fill>

### Step 4 — Verify probes (isolated api)

Observed inside isolated api container:

- `/health`:  200
- `/ready`:   200
- `/metrics`: 200

---

### RPO / RTO (measured)

- RPO: <fill>
- RTO_total: <fill>

### Issues / notes

- <fill>

### Result

PASS

