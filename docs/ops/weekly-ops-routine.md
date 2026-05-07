## Weekly ops routine

The ops surface is now large enough that operators need a recurring
checklist rather than tribal knowledge. This is the canonical "what we
do every week" doc. Run it on a fixed weekday (recommended: Monday
morning UTC, before standup).

### Cadence

| Task                          | Cadence | Tool / runbook                                              | Pass criterion                           |
| ----------------------------- | ------- | ----------------------------------------------------------- | ---------------------------------------- |
| Backup + encrypt              | Daily   | `scripts/ops/pg_backup_encrypt.sh`                           | New `backups/*.dump.age` + sidecars; manifest PASS |
| Off-host copy (backup)        | Daily   | `scripts/ops/offhost_copy.sh` / `docs/ops/offhost-backup-runbook.md` | `sha256sum -c` PASS at DEST              |
| Restore-verification drill    | Daily*  | `scripts/ops/scheduled_restore_drill.sh` (cron)             | Latest report `result == "PASS"`         |
| Drill loop confidence check   | Weekly  | `make restore-drill-loop-validate`                          | Exits 0; "PASS: loop validation"         |
| Evidence retention apply      | Weekly  | `make evidence-retention-apply`                             | Exits 0; archived FAIL reports preserved |
| Backup retention apply        | Monthly | `make backup-retention-apply`                               | Dry-run reviewed first; exits 0          |
| Alerts vs SLO sanity check    | Weekly  | `docs/ops/alerts-slo-alignment.md` re-read                  | No new SLO without an alert (or doc'd gap)|
| Backup manifest spot-check    | Weekly  | `make verify-backup-manifest MANIFEST=<latest>`             | Exits 0; provenance fields populated     |
| Cutover preflight rehearsal   | Before any prod change | `make prod-preflight` against staging              | Exits 0                                  |
| Soak run review               | Weekly  | Latest soak report under `docs/ops/`                        | p95 < 500ms; 5xx < 1%; ready 100%        |

\* "Daily" only on hosts that have the decryption key. On hosts without
the key, weekly is acceptable but document the cadence in the host's
own ops notes.

### Expected signals (what is normal vs. anomalous)

#### Restore drill JSON reports

Location: `artifacts/reports/restore-drills/<UTC>.json`

Normal:

- `result == "PASS"` 6+ days a week.
- `restore_seconds` stable within ±20% week-over-week.
- `manifest_verified == true`.

Anomalous (investigate):

- Any `FAIL` (which the retention script *moves to `archive/`*; it
  doesn't delete).
- `restore_seconds` doubling without an obvious cause (image rebuild,
  schema growth).
- `manifest_verified == false` but `result == "PASS"` — should be
  impossible; if it happens, the drill orchestrator has a bug.

#### Alerts

Normal: no firings during a steady-state week.

Investigate:

- `CasinoBotReadyDown` firing → DB readiness incident, see
  `docs/runbooks/db-readiness-failure.md`.
- `CasinoBotHTTP5xxSpike` firing → see
  `docs/runbooks/http-5xx-spike.md` (M6W1 fix).
- `CasinoBotDeadLetterGrowth` firing → see
  `docs/runbooks/webhook-dead-letter.md`.

#### Backups (off-host)

Normal: daily encrypted artifact under `backups/` (or off-host
destination), each with its `.sha256` + `.meta.json` sidecars; manifest
schema version 2; `git_sha` and `alembic_revision` populated.

Investigate:

- A day without a fresh artifact.
- Manifest with empty `git_sha`/`alembic_revision` after a backup host
  was supposed to be a git checkout (see `scheduled-restore-drill.md`
  — `REQUIRED_MANIFEST_FIELDS`).
- A `.sha256` sidecar disagreeing with the manifest (caught by
  `verify_backup_manifest.py`).

### Quick command reference

```bash
# Everything below is no-Docker except where flagged (docker).

# Weekly, in order:
make restore-drill-loop-validate        # ITERATIONS=5 KEEP_LAST=3 by default
make evidence-retention-dry-run         # review what will be archived/deleted
make evidence-retention-apply           # apply

# Daily (backup host):
./scripts/ops/pg_backup_encrypt.sh

# Daily (backup host) off-host copy:
LATEST=$(ls -1t backups/*.dump.age backups/*.dump.gpg | head -n1)
BACKUP_FILE="$LATEST" BACKUP_DEST=<local dir | user@host:/path/> \
  ./scripts/ops/offhost_copy.sh

# Spot-check the latest backup manifest:
LATEST=$(ls -1t backups/*.dump.age backups/*.dump.gpg | head -n1)
make verify-backup-manifest MANIFEST="$LATEST"

# (docker) Real isolated restore drill:
make scheduled-restore-drill \
  AGE_IDENTITY_FILE="$HOME/.config/casino_bot/age-identity.txt"

# Before any prod change (docker not strictly required; targets a real
# external HTTPS endpoint):
make prod-preflight \
  BASE_URL=https://<staging-domain> \
  HOST_HEADER=<staging-domain> \
  METRICS_BASIC_AUTH=user:pass \
  INSECURE_TLS=true
```

### Cron / systemd examples (operators)

Cron (daily restore drill at 04:30 UTC; weekly retention apply on Mondays):

```bash
# /etc/cron.d/casino_bot_ops (example)
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# Daily restore-verification drill (requires decrypt key on host)
30 4 * * * casino_bot cd /opt/casino_bot && ./scripts/ops/scheduled_restore_drill.sh >> /var/log/casino_bot/restore_drill.log 2>&1

# Weekly evidence retention apply (safe: non-PASS is archived, PASS is trimmed)
15 5 * * 1 casino_bot cd /opt/casino_bot && APPLY=true ./scripts/ops/evidence_retention.sh >> /var/log/casino_bot/evidence_retention.log 2>&1
```

systemd timer (optional; gives journald logs and better failure visibility):

- Use `scripts/ops/scheduled_restore_drill.sh` as the `ExecStart=...`
- Keep secrets out of the unit file; pass only file paths (e.g. `AGE_IDENTITY_FILE=/etc/casino_bot/age-identity.txt`)

### Reviewing a week of evidence

After applying retention, the working set is small:

- `artifacts/reports/restore-drills/*.json` — last `KEEP_LAST` PASS
  reports.
- `artifacts/reports/restore-drills/archive/*.json` — every FAIL ever
  produced (intentional; do **not** wipe this directory).

A 5-minute weekly review is:

1. `cat` the newest PASS report; sanity-check timestamps and
   `restore_seconds`.
2. `ls archive/` — count FAIL reports added since last week (should be
   zero in steady state).
3. If any new FAIL: instantiate the cutover-simulation-report-template
   pattern (or a dedicated incident note) and link the report.

### Related docs

- `docs/ops/scheduled-restore-drill.md`
- `docs/ops/scheduled-restore-drill-report-template.md`
- `docs/ops/backup-retention-policy.md`
- `docs/ops/offhost-backup-runbook.md`
- `docs/ops/compose-reproducibility-audit.md`
- `docs/ops/alerts-slo-alignment.md`
- `docs/ops/cutover-simulation-report-template.md`
- `docs/ops/slo.md`
- `docs/runbooks/*.md`
