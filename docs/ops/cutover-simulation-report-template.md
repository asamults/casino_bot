## Cutover simulation report — TEMPLATE (M6W1)

Use this template for each dry-run cutover rehearsal. Save the
instantiated copy as `cutover-simulation-report-YYYY-MM-DD.md` next to
this file.

> A dry-run cutover **does not** flip production traffic; it exercises
> the full preflight + readiness contract against an external
> staging/canary stack. PASS here is the precondition for actually
> cutting over.

### Run identity

- Date (UTC):           `YYYY-MM-DD HH:MM:SSZ`
- Operator:             `<name>`
- Target stack:         `<staging | canary>`
- Target BASE_URL:      `https://<staging-domain>`
- HOST_HEADER:          `<staging-domain>`
- Compose stack:        `docker-compose.staging.yml` (or external)
- Last commit (main):   `<git_sha>`

### Inputs / env

```bash
export BASE_URL=https://<staging-domain>
export HOST_HEADER=<staging-domain>
export METRICS_BASIC_AUTH=user:pass        # required unless METRICS_PUBLIC=true
export INSECURE_TLS=true                   # only for self-signed staging certs
export CORS_TEST_ORIGIN=https://admin.<staging-domain>
export LEGACY_ENDPOINTS=/admin/ping        # comma-separated; add /admin/login etc.
```

### Preflight result

Command run:

```bash
make prod-preflight
# or directly: ./scripts/ops/production_preflight.sh
```

PASS / FAIL: `<...>`

If FAIL, paste the failing line and the fix taken before re-running.

### Per-check results

| Check                                                    | Result | Notes                  |
| -------------------------------------------------------- | ------ | ---------------------- |
| Required env vars present                                | PASS   |                        |
| `ENVIRONMENT == production`                              | PASS   |                        |
| `validate_env_contract.py`                               | PASS   |                        |
| `GET /health == 200`                                     | PASS   |                        |
| `GET /ready == 200`                                      | PASS   |                        |
| CORS preflight (OPTIONS) returns ACAO + ACAM             | PASS   | Origin: <...>          |
| `/metrics` policy enforced                               | PASS   | basic auth / public    |
| Legacy `/admin/*` Deprecation+Sunset headers present     | PASS   | endpoints: <...>       |

### Adjacent verifications (non-blocking; nice to have)

- Restore drill (latest backup, isolated stack):  PASS / FAIL / NOT-RUN
  → `make scheduled-restore-drill` or manual.
- Backup manifest verify (latest):  PASS / FAIL / NOT-RUN
  → `make verify-backup-manifest MANIFEST=...`
- Smoke drill (`./scripts/drill/smoke.sh`):  PASS / FAIL / NOT-RUN

### Decision

- ✅ Proceed with cutover.
- ⛔ Hold; remediate findings, re-run preflight, then re-evaluate.

### Sign-off

- Reviewed by: `<name>`
- Closed at:   `YYYY-MM-DD HH:MM:SSZ`
- Linked tickets: `<...>`
