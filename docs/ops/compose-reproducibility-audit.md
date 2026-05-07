## Compose / runtime reproducibility audit (M5W4)

Scope: every `docker-compose*.yml` in the repo, audited for the things
that make a Compose deploy reproducible across environments and across
restarts:

1. **Image pinning** — exact version tags, no floating `latest`.
2. **Deterministic startup order** — `depends_on` with a `condition`,
   not just bare service names.
3. **Health-gated dependencies** — downstream services wait until the
   upstream service is `service_healthy`, not just running.
4. **Restart policies** — explicit `restart` directives where the
   service is supposed to survive container/host restarts.
5. **Profiles** — services that are not part of the default stack are
   gated behind named profiles.

The audit is **mostly green**: M5W2/W3 work has already aligned things.
This doc records the per-service status, decisions, and one minor
follow-up.

### Inventory

Files audited (4): `docker-compose.yml`, `docker-compose.override.yml`,
`docker-compose.prod.yml`, `docker-compose.staging.yml`,
`docker-compose.restore.yml`.

| Compose file | Service    | Image pin            | Restart  | Healthcheck | Depends-on condition           | Profile      |
| ------------ | ---------- | -------------------- | -------- | ----------- | ------------------------------ | ------------ |
| `compose.yml`         | postgres   | `postgres:16.11`     | `always` | yes         | n/a                            | (default)    |
| `compose.yml`         | api        | (built, repo)        | (none)   | yes         | postgres: `service_healthy`    | (default)    |
| `compose.yml`         | prometheus | `prom/prometheus:v2.55.1` | (none) | no       | api: (basic)                   | `monitoring` |
| `compose.yml`         | grafana    | `grafana/grafana:11.4.0`  | (none) | no       | prometheus: (basic)            | `monitoring` |
| `compose.prod.yml`    | postgres   | `postgres:16.11`     | `always` | yes         | n/a                            | (default)    |
| `compose.prod.yml`    | api        | (built, repo)        | `always` | yes         | postgres: `service_healthy`    | (default)    |
| `compose.staging.yml` | postgres   | `postgres:16.11`     | `always` | yes         | n/a                            | (default)    |
| `compose.staging.yml` | api        | (built, repo)        | `always` | yes         | postgres: `service_healthy`    | (default)    |
| `compose.staging.yml` | nginx      | `nginx:1.27-alpine`  | `always` | no          | api: (basic, no condition)     | (default)    |
| `compose.restore.yml` | postgres   | `postgres:16.11`     | (none)   | yes         | n/a                            | (default)    |
| `compose.restore.yml` | api        | (built, repo)        | (none)   | yes         | postgres: `service_healthy`    | (default)    |

`docker-compose.override.yml` only adds a dev volume mount + reload
command for `api`; no images, no policies.

### Findings (decisions and rationale)

**Image pinning — PASS.**
Every external image uses an exact, immutable tag.
No `latest`. No floating major/minor tags. Locally-built images
(`api`) are reproducible from the repo's Dockerfile.

**Deterministic startup order — PASS for the data path.**
The `api` service in every environment depends on postgres with
`condition: service_healthy`, so it cannot serve traffic until the DB
healthcheck passes. This is the invariant we care about.

**Health-gated dependencies — PASS for `api`/postgres in all four files.**

**Restart policies — INTENTIONAL DIVERGENCE, accepted.**
- `prod` and `staging`: `restart: always` everywhere. ✓
- `dev` (`compose.yml` + `override.yml`): no `restart`. Intentional —
  developers want explicit start/stop semantics; auto-restart fights
  iterative dev workflows.
- `restore` (`compose.restore.yml`): no `restart`. Intentional — the
  stack is ephemeral; the orchestrator (`restore_isolated_compose.sh`)
  tears it down on success and leaves it standing on failure for
  inspection. Auto-restart would mask failures.
- `monitoring` profile services in dev: no `restart`. Intentional —
  they're already opt-in via profile.

**Profiles — PASS.**
Prometheus and Grafana sit under `profiles: ["monitoring"]` so they
don't run on a plain `docker compose up`. This is what we want for the
default dev experience.

### Minor follow-up (NOT a milestone blocker)

`docker-compose.staging.yml` has:

```yaml
nginx:
  depends_on:
    - api
```

This is the **basic** form of `depends_on` (no `condition`). nginx will
start as soon as the `api` container starts, not when `/ready` returns
200, so during a deploy there's a small window where nginx can return
502s before the api is actually ready. The api healthcheck has a 60s
`start_period`, so this matters in practice.

Recommended fix (single line):

```yaml
nginx:
  depends_on:
    api:
      condition: service_healthy
```

Not done in M5W4 because changing staging compose semantics needs a
manual smoke pass on the staging host (M3 staging-rehearsal flow). It is
queued as a one-line follow-up and explicitly tracked in this audit doc.

### What this audit does NOT cover

- Network segmentation (we use the default Compose bridge in dev/staging;
  prod is single-host).
- Resource limits (memory/cpu). None configured; acceptable for the
  current single-host deployment.
- Volumes / data lifecycle: covered separately by the M5W1/W2/W3 work
  (`backup-restore-compose-runbook.md`,
  `offhost-backup-runbook.md`, `backup-retention-policy.md`).
- Secrets (Docker secrets vs. env vars): covered by
  `docs/ops/secrets-policy.md` and `docs/ops/secrets-inventory.md`.

### Verdict

PASS at the M5W4 maturity level. One queued one-line follow-up (`nginx`
condition in staging) is documented and not in scope.
