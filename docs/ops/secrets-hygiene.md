## Secrets hygiene (M6W2)

This is the *path-level* hygiene policy — what kinds of files MUST NOT
be in the repo, ever, and how the team enforces it. For the principles
("no secrets in git", "rotate on compromise") see
`docs/ops/secrets-policy.md`. For the inventory of secret env vars see
`docs/ops/secrets-inventory.md`.

### What this layer prevents

- Accidental commit of `.env.prod` or `.env.staging`.
- Encrypted backup blobs (`*.dump.age`) being checked in.
- Operational evidence (`artifacts/`) leaking into history.
- TLS keys, htpasswd files, and age/gpg identities being committed.

It does **not** scan content for high-entropy strings. That's a
separate concern (out of scope for this milestone; see "Future work").

### Forbidden paths (the gate)

The full list lives in `scripts/ops/secrets_hygiene_check.sh`. As of
M6W2:

| Pattern                       | Why                                              |
| ----------------------------- | ------------------------------------------------ |
| `backups/`                    | encrypted dumps + sidecars (M5W2)                |
| `artifacts/`                  | drill reports / evidence (M5W4)                  |
| `*.dump`, `*.dump.age`, `*.dump.gpg` | postgres dumps (plain or encrypted)       |
| `.env`, `.env.prod`, `.env.staging`, `.env.offhost`, `.env.restore` | runtime secrets |
| `*.htpasswd`                  | proxy basic-auth credentials                     |
| `**/tls/*.key`, `*.pem`, `*.crt` | TLS material for the external proxy           |
| `**/age-identity*`, `**/*.age.key`, `**/*.gpg.passphrase` | backup decryption keys |

Patterns are matched against:

1. Files **tracked** by git (catches "the file is in history but
   `.gitignore` was added later" regressions).
2. Files **untracked but not gitignored** (catches "operator forgot to
   gitignore a new artifact type before committing").

### How it's enforced

#### CI gate

`scripts/ops/secrets_hygiene_check.sh` runs as a step in
`.github/workflows/security-gates.yml`. If any file matches a forbidden
pattern, CI fails with exit code 3 and a per-file violation list.

#### Local

```bash
./scripts/ops/secrets_hygiene_check.sh
# or, via Make:
make secrets-hygiene-check
```

Exit codes:

- `0` — clean.
- `2` — bad input (script bug; report it).
- `3` — forbidden paths found; details printed to stderr.

#### Optional: pre-commit hook

If you use `pre-commit` locally, add this entry to `.pre-commit-config.yaml`
(not committed by default — opt-in per developer):

```yaml
- repo: local
  hooks:
    - id: secrets-hygiene-check
      name: secrets hygiene (forbidden paths)
      entry: scripts/ops/secrets_hygiene_check.sh
      language: system
      pass_filenames: false
```

### Adding to the forbidden list

When introducing a new artifact type that must never be committed:

1. Add a pattern to `FORBIDDEN_PATTERNS` in
   `scripts/ops/secrets_hygiene_check.sh`.
2. Add the same pattern to `.gitignore` so day-to-day workflows don't
   trip the gate.
3. Add a row to the table above with a one-line "Why".
4. Verify locally:

   ```bash
   # Synthetic positive test (should fail with rc=3):
   touch /tmp/synth/<your-artifact-name>
   ROOT=/tmp/synth ./scripts/ops/secrets_hygiene_check.sh
   ```

### Removing from the forbidden list (rare)

Don't. If a path is forbidden, it stays forbidden — that's the point
of a hygiene gate. The exception is renames: if `.env.staging` becomes
`.config/staging.env`, update the pattern, don't delete it.

### Whitelist mechanism

The script accepts an `IGNORE` env var (comma-separated paths) for
narrow exceptions. Use sparingly and document each entry inline; the
intended use case is example/template files that a new pattern
accidentally matches.

```bash
IGNORE=ops/example/.env.example ./scripts/ops/secrets_hygiene_check.sh
```

### What to do if the gate fires

#### In CI

The job log lists the offending paths. For each:

1. Is this a real secret? → **Stop the merge**, rotate the secret,
   remove the file (`git rm`), and rewrite history if it was already
   pushed (`git filter-repo`).
2. Is it an example/template? → Rename it to make its example-ness
   obvious (`.env` → `.env.example`, etc.).
3. Is it a new artifact type that should be ignored? → Add to
   `.gitignore`, re-run.

#### Locally before commit

Same logic, but at no merge cost. The pre-commit hook above is the
cheap way to catch it before `git push`.

### Related work / future

- Content scanning (e.g. `gitleaks`, `detect-secrets`) is the natural
  complement: it catches plaintext secrets *inside* files, not just
  forbidden paths. Out of scope for M6W2; tracked separately.
- Sealed-secrets / SOPS-encrypted committed secrets are a controlled
  form of "secret in git that's safe to commit". If we adopt either,
  this policy needs an explicit allowed pattern (e.g.
  `**/*.sops.yaml`).
