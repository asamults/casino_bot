## Restore-drill loop validation (M6W1)

### Why this exists

The M5W4 work introduced `scheduled_restore_drill.sh` and
`evidence_retention.sh`. Each was unit-tested in isolation. M6W1 adds a
**confidence-over-time** loop validation: run the drill back-to-back N
times, mix in synthesized "prior weeks" PASS reports, then exercise
retention on the combined corpus. The goal is to catch issues that only
appear when the pipeline runs many times (filename collisions, mtime
ordering, retention overshoot, idempotency drift).

### Tooling

`scripts/ops/restore_drill_loop_validate.sh`. No Docker required; uses
the no-backup branch of `scheduled_restore_drill.sh` which produces a
`FAIL` report deterministically — sufficient for testing the *report
pipeline* without spinning up a Postgres restore.

### What it asserts

1. Each iteration writes a uniquely-named JSON report (filename =
   UTC second-resolution timestamp; the harness sleeps 1s between
   iterations to avoid clobbering).
2. Every report parses as JSON and contains the M5W4 required fields
   (`schema_version`, `result`, `reason`, `backup_dir`, `backup_file`,
   `manifest_verified`, `isolated_project`, `started_at_utc`,
   `ended_at_utc`, `duration_seconds`).
3. After `evidence_retention.sh APPLY=true`:
   - At most `KEEP_LAST` PASS reports remain at the top level.
   - All FAIL reports are moved to `archive/`, never deleted.
4. A second `APPLY=true` is idempotent (no further state change).

### Sample run

```bash
ITERATIONS=5 KEEP_LAST=3 PRIOR_PASS=4 \
  OUT_DIR=/tmp/m6w1_loop_demo \
  ./scripts/ops/restore_drill_loop_validate.sh
```

Output (abbreviated):

```
== restore_drill_loop_validate ==
Iterations:    5
Prior PASS:    4 (synthetic)
Keep last:     3
Working dir:   /tmp/m6w1_loop_demo

-- running drill loop --
  iteration 1/5
  iteration 2/5
  iteration 3/5
  iteration 4/5
  iteration 5/5
-- generated 9 reports total (4 prior + 5 new)
  ok   all 9 reports are well-formed
-- retention dry-run (KEEP_LAST=3) --
-- retention apply --
  ok   3 PASS reports remain (<= KEEP_LAST=3)
  archived FAIL reports: 5

== summary ==
  iterations:        5
  total reports:     9
  remaining top-lvl: 3
  archived FAIL:     5
PASS: loop validation
```

### Sample report shapes

PASS report (synthesized prior-weeks fixture; same shape as a real
drill PASS). Filename, JSON timestamps, and on-disk mtime are all
derived from the same epoch (`now - i * 86400`), so a file named
`20260504T182501Z.json` will always carry matching `started_at_utc`
and a matching mtime.

```json
{
  "schema_version": 1,
  "result": "PASS",
  "reason": "ok",
  "backup_dir": "/synthetic",
  "backup_file": "/synthetic/x.dump.age",
  "manifest_verified": true,
  "isolated_project": "casino_bot_restore_synthetic_3",
  "started_at_utc": "2026-05-04T18:25:01Z",
  "ended_at_utc":   "2026-05-04T18:26:01Z",
  "duration_seconds": 60,
  "verify_seconds": 1,
  "restore_seconds": 59,
  "host_header": "api.example.com",
  "compose_file": "docker-compose.restore.yml",
  "env_file": ".env.restore.example"
}
```

FAIL report (real drill output on the no-backup test path; identical
shape applies to a real Docker restore failure):

```json
{
  "schema_version": 1,
  "result": "FAIL",
  "reason": "no encrypted backups found in BACKUP_DIR",
  "backup_dir": "/tmp/m6w1_loop_demo/backups",
  "backup_file": "",
  "manifest_verified": false,
  "isolated_project": "",
  "started_at_utc": "2026-05-07T18:10:43Z",
  "ended_at_utc": "2026-05-07T18:10:43Z",
  "duration_seconds": 0,
  "verify_seconds": 0,
  "restore_seconds": 0,
  "host_header": "api.example.com",
  "compose_file": "docker-compose.restore.yml",
  "env_file": ".env.restore.example"
}
```

### How to read the result

- `PASS: loop validation` — the drill+retention pipeline survives a
  many-week simulation; safe to leave running on cron.
- `FAIL: loop validation` — something regressed. Check the per-iteration
  log under `OUT_DIR/drill_<n>.log` and the retention dry-run /
  apply output under `OUT_DIR/retention_*.out`.

### Limitations

- This loop **does not** verify that a real Docker restore succeeds.
  That's a Docker-bound exercise covered by
  `scripts/ops/restore_isolated_compose.sh` and the scheduled drill
  itself. The loop is intentionally Docker-free so it can run in CI as
  a regression gate (see `scripts/ops/ops_contract_smoke.sh`).
- Iterations are spaced 1s apart to keep filenames unique. A real cron
  cadence (daily/weekly) is much sparser; collisions are not a concern
  in practice.
