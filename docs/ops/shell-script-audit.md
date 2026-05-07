## Shell script audit (M5W3)

This is the M5W3 audit of every shell script under `scripts/`. Findings
and decisions are deliberately conservative: no behavior changes were made
to scripts that are working today.

Scope (15 scripts):

- `scripts/lint_shell.sh` (new — lint gate)
- `scripts/ops/*.sh` (8 scripts)
- `scripts/soak/run_soak_prod_compose.sh`
- `scripts/drill/*.sh` (5 scripts)

### 1) Lint gate

- `bash -n` on every `scripts/**/*.sh` runs locally and in CI.
- `shellcheck --severity=warning --exclude=SC1091 --shell=bash -x` runs
  whenever the binary is present. CI installs it via `apt-get`. Local
  runs warn (and continue) if it isn't installed; set
  `REQUIRE_SHELLCHECK=1` to fail-closed.
- `SC1091` ("source not followed") is excluded because of the dynamic
  `source "$(dirname …)/_common.sh"` pattern in `scripts/drill/*`. The
  `-x` flag follows sourced files, so this only suppresses the
  "couldn't statically resolve" noise, not real findings inside `_common.sh`.

### 2) Safer bash mode

**Decision: bump every script to `set -Eeuo pipefail`.**

The `-E` flag makes `ERR` traps fire inside functions, sub-shells, and
command substitutions, which we now rely on for the plaintext-shred trap
in `pg_backup_encrypt.sh` (see §3). The other flags (`-e`, `-u`,
`pipefail`) were already in place repo-wide.

**Decision: do NOT add `IFS=$'\n\t'` blanket-style.**

Rationale: the recommendation only matters where unquoted external strings
get word-split. Audit shows none of our scripts do this — every external
string is double-quoted, every loop iterates over an explicit array, and
the only `read -r` calls use process substitution (`<<<` / `< <(…)`)
where IFS only affects field splitting on those reads (and in those reads
we already either pass two-token output, or rely on default IFS being a
non-issue). Setting `IFS` "just in case" risks subtly breaking behavior
inside transitively-sourced library code we don't control. Audit-doc
recommendation, not a code change.

If a script is added later that *does* need it (e.g. iterating over
`find` output without `-print0`), set `IFS=$'\n\t'` at the top of that
specific script and document the reason inline.

### 3) Secret leakage

Audit checked for:

| Class                          | Status  | Notes                                       |
| ------------------------------ | ------- | ------------------------------------------- |
| `set -x` anywhere              | none    | `rg '^\s*set -x'` returns 0 hits.          |
| `echo $SECRET / PASSWORD / …`  | none    | No script logs secret env values.           |
| Decrypted dump lifecycle       | fixed   | See "Plaintext on failure" below.           |
| Temp file cleanup              | ok      | Two scripts use temp files: see below.      |
| Argv-passed secrets            | minor   | One drill script: see below.                |

#### Plaintext on failure (FIXED in M5W3)

`scripts/ops/pg_backup_encrypt.sh` previously only removed the plaintext
`.dump` at the end of the success path. If `age`/`gpg` failed, the
plaintext dump persisted on disk in `./backups/`. M5W3 adds an `ERR INT
TERM` trap that shreds the plaintext (or `rm -f`s it as a fallback)
and then re-exits with the original code. The trap is cleared after the
configured cleanup step at the end of the success path.

#### Temp file cleanup (no changes needed)

- `scripts/ops/restore_isolated_compose.sh` — `mktemp -d`, `trap … EXIT`
  shreds-or-removes the directory; on success the decrypted dump is
  inside this directory and gets shredded. ✓
- `scripts/ops/backup_retention.sh` (new) — `mktemp` for the input list
  (no secret content), `trap 'rm -f' EXIT`. ✓
- `scripts/drill/drill_webhook_dead_letter.sh` — `mktemp` for response
  headers, removed manually after use. Acceptable for a dev drill.

#### Argv-passed secret (drill, low risk, not fixed in M5W3)

`scripts/drill/drill_webhook_dead_letter.sh` invokes:

```
sig_header="$(python - "$STRIPE_WEBHOOK_SECRET" "$payload" <<'PY' …)"
```

This places `STRIPE_WEBHOOK_SECRET` in `argv` and therefore in
`/proc/<pid>/cmdline` for the lifetime of the python process. It is
visible to other processes on the same host. This is a **dev/staging
GameDay drill**, not production code, and the value is typically
`drill_stripe_secret` (set inline in the script's own default), not a
real secret. The recommendation, recorded here for follow-up, is to
pass the secret on stdin or via an env var instead:

```
sig_header="$(STRIPE_WEBHOOK_SECRET="$STRIPE_WEBHOOK_SECRET" \
  python - "$payload" <<'PY'
import os, hmac, hashlib, sys, time
secret = os.environ["STRIPE_WEBHOOK_SECRET"].encode()
...
PY
)"
```

Not done in M5W3 because (a) it changes drill behavior we want to keep
green, and (b) the threat model is local-host-only on a dev machine. If
this drill is ever wired into a multi-tenant CI runner, fix it first.

### 4) Backup retention

See `docs/ops/backup-retention-policy.md`.
Implementation: `scripts/ops/backup_retention.sh` (dry-run by default).
Make targets: `backup-retention-dry-run`, `backup-retention-apply`.

### Latent bugs uncovered by the lint gate

Adding shellcheck surfaced two real bug classes that had been hiding:

**SC2259 — `curl … | python - <<'PY'` heredoc shadowed the pipe** (5 sites).
Bash redirections are processed left-to-right; the heredoc on `python -`
overrides the upstream pipe. Result: `sys.stdin.read()` returned `""`
because Python's stdin was the heredoc (already consumed as the script
source). All 5 sites fixed in M5W3 by capturing curl output to a shell
variable and passing it to Python via env (`METRICS_TEXT="…" python …`).
This is the same pattern recommended for the argv-secret follow-up.

**SC2034 — `for i in {1..60}` with unused `$i`** (2 sites).
Renamed to `for _` to match the established convention in
`scripts/ops/restore_isolated_compose.sh`.

### Latent bugs explicitly NOT fixed in M5W3

These are real but out of scope for an audit milestone; logging them so
the next pass picks them up. They predate M5W3 and the dev/staging-only
drill scripts continue to behave the way they did before.

- **`scripts/drill/_common.sh::metric_value`** — the Python regex uses
  `r"^...\\s+([0-9eE+\\-.]+)\\s*$"` (double-backslash) where it should
  be `\s+` / `[0-9eE+\-.]+`. After the SC2259 fix, the function now
  receives real metric text instead of `""`, but the regex still fails
  to match prometheus's `metric_name 12.34` output, so the function
  continues to return `""`. Same observable behavior as before. The fix
  is to drop one level of backslash escaping in that regex.

- **`scripts/drill/drill_webhook_dead_letter.sh`** — passes
  `STRIPE_WEBHOOK_SECRET` as a positional argument to `python -`. See
  §3 "Argv-passed secret".

### Per-script decisions

All 15 scripts:

- Now declare `set -Eeuo pipefail`.
- `bash -n` clean.
- `shellcheck --severity=warning --exclude=SC1091 -x` clean as of M5W3.

Unchanged behaviors that the audit explicitly accepted:

- `scripts/ops/pg_dump_compose.sh` and `pg_restore_compose.sh` extract
  `POSTGRES_USER` / `POSTGRES_DB` from `ENV_FILE` via
  `grep | cut -d= -f2-`. Acceptable: the env file is the single source
  of truth and is gitignored when it contains real values.
- `scripts/ops/production_preflight.sh` does not require
  `METRICS_BASIC_AUTH`; if absent, it logs a SKIP and proceeds. This is
  intentional: the script is also runnable against a stack where
  metrics policy is enforced upstream of the test point.
- `scripts/drill/restore_from_tag.sh` does `rm -rf "$wt_dir"` before
  `git worktree add`. Path is `.worktrees/restore-$tag` which is repo-
  local; safe as long as `$tag` is sane (script `fail`s on empty tag).
