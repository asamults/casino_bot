## Cutover simulation report — 2026-05-07 (sample dry-run)

This is a sample instantiation of `cutover-simulation-report-template.md`
for the M6W1 milestone. It documents what a real dry-run cutover
preflight produces, **without an actual external staging stack
provisioned in this environment**. Sections that would be filled in
against a real stack are marked `(stack-required)`.

### Run identity

- Date (UTC):           2026-05-07 18:00:00Z
- Operator:             milestone owner
- Target stack:         simulated (no external HTTPS endpoint reachable
                        from the dev sandbox)
- Target BASE_URL:      `https://staging.example.invalid` (placeholder)
- HOST_HEADER:          `staging.example.invalid`
- Compose stack:        `docker-compose.staging.yml`
- Last commit (main):   `75c6c2c` (M5W4)

### Inputs / env

```bash
export BASE_URL=https://staging.example.invalid
export HOST_HEADER=staging.example.invalid
export METRICS_BASIC_AUTH=metrics:notarealsecret
export INSECURE_TLS=true
export CORS_TEST_ORIGIN=https://admin.staging.example.invalid
export LEGACY_ENDPOINTS=/admin/ping        # add more as routes are deprecated
```

### Preflight result

Command:

```bash
make prod-preflight
```

Status: **PRECONDITION** — the preflight script itself is locally
validated by `bash -n`, `shellcheck`, and the new `ops_contract_smoke`
gate. Running it against a real staging stack on cutover day is the
final confirmation step.

### Per-check results (what the script enforces)

The M6W1 preflight enforces all of the following in this order. Any
single FAIL exits 2 immediately:

| Check                                                    | Where (`production_preflight.sh`)              |
| -------------------------------------------------------- | ---------------------------------------------- |
| Required env vars present                                | `--- 1) required env vars ---`                 |
| `ENVIRONMENT == production`                              | same block                                     |
| `validate_env_contract.py`                               | "Validating env contract"                      |
| `GET /health == 200`                                     | "GET /health"                                  |
| `GET /ready == 200`                                      | "GET /ready"                                   |
| CORS preflight (OPTIONS) returns ACAO + ACAM             | "-- CORS preflight (OPTIONS) --"               |
| `/metrics` policy enforced (auth or `METRICS_PUBLIC=true`) | "-- /metrics policy --"                      |
| Multiple legacy endpoints emit `Deprecation`+`Sunset`    | "-- Legacy deprecation headers --"             |

### What changed in M6W1 vs. prior preflight

1. CORS preflight check added. The script now sends an `OPTIONS` request
   with an `Origin:` derived from `CORS_TEST_ORIGIN` (or, failing that,
   the first entry of `CORS_ALLOW_ORIGINS`) and asserts that the
   response carries both `Access-Control-Allow-Origin` and
   `Access-Control-Allow-Methods`. The allow-origin must echo the
   requested origin (browsers reject `*` for credentialed CORS).
2. `/metrics` policy is now **fail-closed**. Previously, if
   `METRICS_BASIC_AUTH` wasn't set, the check SKIPPED — a real misconfig
   would slip through. Now the script FAILS unless either basic auth is
   provided (and verified to be enforced) or `METRICS_PUBLIC=true` is
   explicitly opted in.
3. Legacy deprecation header check accepts a comma-separated list via
   `LEGACY_ENDPOINTS`. Default is `/admin/ping`; teams add more paths
   as routes are formally marked legacy.

### Adjacent verifications

- `ops_contract_smoke`: PASS (13/13) — see CI step / `make ops-contract-smoke`.
- `restore_drill_loop_validate` (5 iterations + retention): PASS
  — see `docs/ops/restore-drill-loop-validation.md`.
- Backup manifest verify on synthetic fixture: PASS
  — covered by `tests/test_ops_backup_manifest.py` (12 cases).

(stack-required) On a real cutover dry-run also collect:
- Latest scheduled restore drill report (under
  `artifacts/reports/restore-drills/`).
- Smoke drill against the staging stack (`./scripts/drill/smoke.sh`).
- Soak harness output (p95 latency in particular).

### Decision

⛔ Not a real cutover. This is a milestone artifact. The preflight
script is the gating tool; running it green against an external staging
HTTPS endpoint is the cutover precondition.

### Sign-off

- Reviewed by: M6W1 milestone owner
- Closed at:   2026-05-07
- Linked tickets: M6W1
