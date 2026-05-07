## Backup retention policy (M5W3)

Scope: encrypted backup artifacts produced by `scripts/ops/pg_backup_encrypt.sh`
under `./backups/` (`*.dump.age` / `*.dump.gpg`) plus their `.sha256` and
`.meta.json` sidecars. Off-host destinations apply the same policy
independently — see "Off-host destinations" below.

### Defaults

- **Daily**:   keep the newest backup of each of the last **7 UTC dates**.
- **Weekly**:  keep the newest backup of each of the last **4 ISO weeks**.
- **Monthly**: keep the newest backup of each of the last **3 calendar months**.

The kept set is the **union** of those three buckets, deduplicated by
file path. Anything outside that union is a delete candidate.

Selection is deterministic and is based on **mtime of the encrypted file**
(not the timestamp embedded in the filename), so manual `touch` calls or
restored-from-tar artifacts are honored.

### Tooling

- `scripts/ops/backup_retention.sh` — preview / apply.
- Make targets:
  - `make backup-retention-dry-run` — preview only (no deletions). **Default.**
  - `make backup-retention-apply`   — actually delete non-kept artifacts (and sidecars).

Inputs (env): `BACKUP_DIR` (default `./backups`), `DAILY_KEEP`,
`WEEKLY_KEEP`, `MONTHLY_KEEP`, `APPLY=true|false`.

### Operational rules

1. **Always dry-run first.** `make backup-retention-dry-run` lists the
   `--- KEEP ---` and `--- DELETE ---` plan. Eyeball it before applying.
2. **Sidecars follow their parent.** A `.sha256` / `.meta.json` is deleted
   iff its parent encrypted file is deleted.
3. **Mixed formats coexist.** `*.dump.age` and `*.dump.gpg` are pooled into
   the same buckets — if you have one of each on the same UTC day, both
   may be kept (the daily bucket only deduplicates by date, not by tool).
   This is by design: switching encryption tools should not silently
   delete the previous tool's artifact for the same day.
4. **Plaintext leaks are out of scope here.** `pg_backup_encrypt.sh`
   shreds the plaintext `.dump` on success and on error (M5W3 fix).
   Retention only operates on encrypted artifacts.

### Recommended scheduling

- Manual: run weekly during ops review.
- cron (host-side, after you've created at least one verified backup):

  ```
  # Daily 03:30 UTC: prune old encrypted backups (apply mode).
  30 3 * * *  cd /opt/casino_bot && make backup-retention-apply >> var/log/casino_bot/retention.log 2>&1
  ```

- CI/automation: keep this **manual** on the prod host; we do not run
  destructive retention from CI workers.

### Off-host destinations

The local script does not reach out over SSH. For an off-host directory
on a backup server, the recommended pattern is to run the same script
**there**, against that machine's local copy of `backups/`, with its own
schedule. For SSH targets, mount or `rsync` the directory locally and run
the same script.

### Edge cases

- **Empty `BACKUP_DIR`** → script exits 0, no-op.
- **All artifacts within the daily window** → nothing is deleted. This is
  the normal state during the first week after enabling retention.
- **Clock skew** between the host that produced the backup and the host
  running retention → may shift bucket assignment by one day. Acceptable
  given the policy granularity; if it's a real problem, run retention
  only on the host that produced the artifacts.
- **`shred` not installed** → backup encryption already falls back to
  `rm -f`. Retention uses `rm -f` directly; if you need crypto-erase
  semantics, the underlying filesystem must support it (e.g. dm-crypt
  on the backup volume).

### Limitations

This policy does **not**:

- guarantee any RPO (M5W2 set RPO ≈ "time since last successful backup"),
- restore PITR semantics (we have no WAL archiving),
- track off-host capacity / quotas (operational, not policy).

These belong to a later milestone (managed Postgres, WAL archiving, or
object-storage lifecycle policies).
