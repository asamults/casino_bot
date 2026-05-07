## Scheduled restore-verification drill (M5W4)

Scope: take the manual M5W2 pipeline (backup → encrypt → off-host →
isolated restore) and turn the **restore-and-verify** half of it into a
schedulable job that emits an evidence artifact. This is the closing
piece of the operational lifecycle for the no-managed-Postgres,
no-WAL/PITR baseline.

### Components

- `scripts/ops/scheduled_restore_drill.sh` — orchestrator.
- `scripts/ops/verify_backup_manifest.py` — manifest schema + sha256
  validator (used as the first stage of the drill).
- `scripts/ops/restore_isolated_compose.sh` — unchanged, still the
  canonical "restore into an isolated Compose project" implementation.
- `scripts/ops/evidence_retention.sh` — cleans up old reports;
  preserves FAILED reports under `archive/`.

### Flow

1. Pick the newest `*.dump.age` / `*.dump.gpg` from `BACKUP_DIR`
   (default: `./backups`).
2. Run `verify_backup_manifest.py` on its `.meta.json`. Fail closed if
   the schema is wrong, sha256 doesn't match the artifact, or required
   fields are missing.
3. Run `restore_isolated_compose.sh` against the artifact. The restore
   stack is created under `restore_<UTC>` so it cannot
   collide with the running prod project; volumes and networks are
   project-namespaced.
4. Write a structured JSON report to
   `artifacts/reports/restore-drills/<UTC>.json`:

   ```json
   {
     "schema_version": 1,
     "result": "PASS",
     "reason": "ok",
     "backup_dir": "...",
     "backup_file": "...",
     "manifest_verified": true,
    "isolated_project": "restore_20260507T160000Z",
     "started_at_utc": "2026-05-07T16:00:00Z",
     "ended_at_utc":   "2026-05-07T16:01:30Z",
     "duration_seconds": 90,
     "verify_seconds": 1,
     "restore_seconds": 88,
     "host_header": "api.example.com",
     "compose_file": "docker-compose.restore.yml",
     "env_file": ".env.restore.example"
   }
   ```

5. Exit code: 0 on PASS, 2 on bad input (no backups), 3 on verify or
   restore failure.

### Usage

On-demand:

```bash
make scheduled-restore-drill \
  AGE_IDENTITY_FILE="$HOME/.config/casino_bot/age-identity.txt"
```

cron (production host):

```cron
30 4 * * *  cd /opt/casino_bot && \
  ENV_FILE=.env.restore HOST_HEADER=api.example.com \
  AGE_IDENTITY_FILE=/etc/casino_bot/age-identity.txt \
  ./scripts/ops/scheduled_restore_drill.sh \
  >> /var/log/casino_bot/restore_drill.log 2>&1
```

Notes:

- Run this on a host with the **decryption** key, not necessarily the
  production app host.
- The restore stack rebuilds the `api` image, which can be expensive.
  Schedule for off-peak.
- `AGE_IDENTITY_FILE` is required for `.dump.age`. The script defaults
  to `~/.config/casino_bot/age-identity.txt`.

### Required manifest fields

By default the drill accepts the M5W4 default schema (v2 with
best-effort empty `git_sha` / `alembic_revision`). To require strict
provenance (recommended once your backup hosts have git checkout +
running compose):

```bash
REQUIRED_MANIFEST_FIELDS=git_sha,alembic_revision \
  ./scripts/ops/scheduled_restore_drill.sh
```

### Evidence retention

Drill reports accumulate. Use `scripts/ops/evidence_retention.sh`
(default policy: keep last **14** PASS reports; FAIL reports are moved
to `archive/` and never auto-deleted):

```bash
make evidence-retention-dry-run    # preview only
make evidence-retention-apply      # actually delete + archive
```

The intent: a quick "show me this month's drill outcomes" stays
manageable, while incident evidence is preserved by virtue of being
moved into `archive/` on first cleanup pass.

### Limitations

- This drill **does not** restore-to-timestamp; M5W4 still has no WAL
  archiving. RPO is bounded by the cadence of the encrypt pipeline.
- The drill spins up a full restore stack on every run; this costs
  Docker resources. If that becomes a problem, the next iteration is
  to reuse a pre-built api image instead of `--build` on every run.
- Off-host pull is **not** part of this drill. The drill assumes the
  artifact is locally available. To verify "we can pull from off-host
  and then restore", chain `backup_offhost_copy.sh` (in the other
  direction) before this script.

### What "PASS" buys you

Each PASS report is concrete evidence that, **on this date**, against
**this specific encrypted artifact**, the team can:

- decrypt with the configured age/gpg identity,
- verify the sha256 sidecar agrees with the manifest,
- restore into a clean DB,
- run migrations,
- start the api,
- and reach `/health`, `/ready`, `/metrics` on the restored stack.

A streak of green daily/weekly reports is the operational answer to
"do you actually test your backups?"
