## Scheduled restore-drill — incident-review template (M5W4)

Use this template when reviewing the JSON report at
`artifacts/reports/restore-drills/<UTC>.json` (raw artifact lives next
to this template's instantiation).

### Drill identity

- Drill UTC:           `<started_at_utc>` → `<ended_at_utc>`
- Backup file:         `<backup_file>`
- Backup mtime:        <UTC>
- Isolated project:    `<isolated_project>` (e.g. `casino_bot_restore_<UTC>`)
- Compose file:        `<compose_file>`
- Restore env file:    `<env_file>`
- Operator / runner:   <name | cron | ci-job-name>

### Result

PASS / FAIL

### Latencies

- verify_seconds:   <n>   (manifest schema + sha256 over the encrypted blob)
- restore_seconds:  <n>   (decrypt + isolated stack up + pg_restore + readiness)
- duration_seconds: <n>   (end-to-end)

Compare against the M5W2 RPO/RTO baseline:

- Target RTO (this stage, no PITR): ≤ <Y> minutes.
- Observed RTO: <duration_seconds> s.

### Manifest provenance (snapshot at drill time)

- schema_version:    <1|2>
- encryption:        <age|gpg>
- git_sha:           <hex|empty>
- git_describe:      <string|empty>
- postgres_version:  <e.g. 16.11|empty>
- alembic_revision:  <hex|empty>

If any of these are empty and your operational standard requires them,
re-run the drill with `REQUIRED_MANIFEST_FIELDS=git_sha,alembic_revision`
and treat the resulting failure as a backup-pipeline gap, not a
restore-pipeline gap.

### On FAIL

- `reason` field from the JSON: `<reason>`
- Where to look:
  - report: `artifacts/reports/restore-drills/<UTC>.json` (will be
    moved to `archive/` on next `evidence-retention-apply`)
  - drill stdout/stderr: `<log path>` (cron) or scrollback (manual)
  - isolated project containers (if `KEEP_STACK=true`):
    `docker compose -p <isolated_project> -f docker-compose.restore.yml ps`

### Cleanup

- Isolated stack auto-torn-down on PASS. On FAIL, `KEEP_STACK=true` is
  recommended for forensic inspection; clean up manually:

  ```
  docker compose -p <isolated_project> -f docker-compose.restore.yml down -v
  ```

### Sign-off

- Reviewed by: <name>
- Action taken: <none | re-ran | filed incident #...>
- Closed at:  <UTC>
