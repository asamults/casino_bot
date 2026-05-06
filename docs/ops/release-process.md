## Release process (baseline)

### Versioning

- **SemVer**: `MAJOR.MINOR.PATCH`.
- Current API version is tracked in FastAPI `app.version` and the release changelog entry.

### Tag conventions

- **Release tags**: `v<semver>` (example: `v0.2.0`).
- **Milestone tags** (internal): `m<w>-<topic>-<YYYY-MM>` (example: `m3w2-metrics-hardening-2026-05`).

### How to cut a release (manual)

1. Ensure CI is green on `main`.
2. Update `CHANGELOG.md` (move items from `Unreleased` to the new version section).
3. Create an annotated tag:

```bash
git tag -a "v0.2.0" -m "Release v0.2.0"
git push origin "v0.2.0"
```

4. Create a GitHub Release from the tag (see workflow: `.github/workflows/release.yml`).

