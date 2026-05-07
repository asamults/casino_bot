#!/usr/bin/env python3
"""Verify a backup manifest (.meta.json) against its on-disk artifacts.

M5W4: schema v2 manifest validator.

Checks performed (in order):
  1. Manifest file exists and parses as JSON.
  2. `schema_version` is in the supported range (currently 1 or 2).
  3. All required top-level fields for the manifest's declared schema
     version are present and non-empty.
  4. The encrypted artifact referenced by `encrypted_basename` exists in
     the same directory as the manifest.
  5. Recompute sha256(encrypted artifact) and compare against `sha256`.
  6. If a `.sha256` sidecar file is present, parse it and confirm it
     agrees with the manifest's `sha256` value.
  7. Optional: when `--require-fields f1,f2,...` is passed, fail closed
     if any of those fields is empty (default schema v2 fields are
     allowed-to-be-empty for backwards compatibility with hosts that
     can't query postgres at backup time).

Output:
  - On PASS: prints a single line `PASS: <manifest>` and exits 0.
  - On FAIL: prints `FAIL: <reason>` to stderr and exits non-zero.
  - With --json, emits a structured JSON report on stdout (PASS or FAIL)
    and still uses the exit code as the source of truth.

Exit codes:
  0  PASS
  2  bad input / I/O error
  3  validation failure (schema mismatch, missing field, bad checksum)

This script is intentionally dependency-free (stdlib only).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

SUPPORTED_SCHEMA_VERSIONS = (1, 2)

# Required fields per schema version. Values must be non-empty strings or
# (for size fields) non-negative integers.
REQUIRED_FIELDS: dict[int, tuple[str, ...]] = {
    1: (
        "schema_version",
        "created_at_utc",
        "tool",
        "recipient",
        "plaintext_basename",
        "encrypted_basename",
        "plaintext_size_bytes",
        "encrypted_size_bytes",
        "sha256",
        "compose_file",
        "env_file",
        "postgres_service",
    ),
    2: (
        "schema_version",
        "created_at_utc",
        "tool",
        "encryption",
        "recipient",
        "plaintext_basename",
        "encrypted_basename",
        "plaintext_size_bytes",
        "encrypted_size_bytes",
        "sha256",
        "compose_file",
        "env_file",
        "postgres_service",
        "git_sha",
        "git_describe",
        "postgres_version",
        "alembic_revision",
    ),
}

# Fields that are present-but-allowed-to-be-empty in v2 (best-effort
# provenance fields populated only when a backup host can query them).
V2_ALLOWED_EMPTY = {
    "git_sha",
    "git_describe",
    "postgres_version",
    "alembic_revision",
}


class VerifyError(Exception):
    """Raised when a manifest fails validation."""

    def __init__(self, code: int, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


def _sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            buf = fh.read(chunk)
            if not buf:
                break
            h.update(buf)
    return h.hexdigest()


def _load_manifest(manifest_path: Path) -> dict:
    if not manifest_path.is_file():
        raise VerifyError(2, f"manifest not found: {manifest_path}")
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VerifyError(3, f"manifest is not valid JSON: {exc}") from exc


def _check_schema_version(manifest: dict) -> int:
    sv = manifest.get("schema_version")
    if not isinstance(sv, int) or sv not in SUPPORTED_SCHEMA_VERSIONS:
        raise VerifyError(
            3,
            f"unsupported schema_version={sv!r}; "
            f"expected one of {SUPPORTED_SCHEMA_VERSIONS}",
        )
    return sv


def _check_required_fields(manifest: dict, schema_version: int) -> None:
    required = REQUIRED_FIELDS[schema_version]
    missing = [k for k in required if k not in manifest]
    if missing:
        raise VerifyError(3, f"manifest missing required fields: {missing}")

    # Non-empty checks (with v2 allow-empty exemptions).
    bad: list[str] = []
    for k in required:
        v = manifest[k]
        if k in {"plaintext_size_bytes", "encrypted_size_bytes", "schema_version"}:
            if not isinstance(v, int) or v < 0:
                bad.append(f"{k}={v!r} (expected non-negative int)")
            continue
        if schema_version == 2 and k in V2_ALLOWED_EMPTY and v == "":
            continue
        if not isinstance(v, str) or v == "":
            bad.append(f"{k}={v!r} (expected non-empty str)")
    if bad:
        raise VerifyError(3, f"invalid manifest fields: {bad}")


def _check_sha256(manifest: dict, manifest_path: Path) -> tuple[str, str]:
    """Return (computed_sha256, encrypted_path)."""
    enc_basename = manifest["encrypted_basename"]
    enc_path = manifest_path.parent / enc_basename
    if not enc_path.is_file():
        raise VerifyError(
            2, f"encrypted artifact not found next to manifest: {enc_path}"
        )
    actual = _sha256_file(enc_path)
    expected = manifest["sha256"]
    if actual.lower() != expected.lower():
        raise VerifyError(
            3,
            f"sha256 mismatch for {enc_basename}: expected={expected} actual={actual}",
        )
    return actual, str(enc_path)


def _check_sidecar_sha(manifest: dict, manifest_path: Path) -> None:
    sha_path = manifest_path.parent / (manifest["encrypted_basename"] + ".sha256")
    if not sha_path.is_file():
        return
    line = sha_path.read_text(encoding="utf-8").strip().split()
    if not line:
        raise VerifyError(3, f"sha256 sidecar is empty: {sha_path}")
    sidecar_value = line[0].lower()
    if sidecar_value != manifest["sha256"].lower():
        raise VerifyError(
            3,
            f"sha256 sidecar disagrees with manifest: "
            f"sidecar={sidecar_value} manifest={manifest['sha256']}",
        )


def _check_required_fields_strict(manifest: dict, required: list[str]) -> None:
    missing = [k for k in required if not manifest.get(k)]
    if missing:
        raise VerifyError(3, f"--require-fields: empty/missing fields: {missing}")


def verify(manifest_path: Path, require_fields: list[str] | None = None) -> dict:
    manifest = _load_manifest(manifest_path)
    schema_version = _check_schema_version(manifest)
    _check_required_fields(manifest, schema_version)
    actual_sha, enc_path = _check_sha256(manifest, manifest_path)
    _check_sidecar_sha(manifest, manifest_path)
    if require_fields:
        _check_required_fields_strict(manifest, require_fields)
    return {
        "result": "PASS",
        "manifest_path": str(manifest_path),
        "encrypted_path": enc_path,
        "schema_version": schema_version,
        "sha256_verified": actual_sha,
        "git_sha": manifest.get("git_sha", ""),
        "git_describe": manifest.get("git_describe", ""),
        "postgres_version": manifest.get("postgres_version", ""),
        "alembic_revision": manifest.get("alembic_revision", ""),
        "encryption": manifest.get("encryption", manifest.get("tool", "")),
    }


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "manifest",
        help="path to .meta.json (or to .dump.age/.dump.gpg; .meta.json is inferred)",
    )
    p.add_argument(
        "--require-fields",
        default="",
        help="comma-separated list of fields that must be non-empty "
        "(default: empty; standard schema checks always apply)",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="emit a structured JSON report on stdout",
    )
    return p.parse_args(argv)


def _resolve_manifest_path(arg: str) -> Path:
    p = Path(arg)
    if p.suffix == ".json" or p.name.endswith(".meta.json"):
        return p
    # Allow passing the encrypted artifact; infer .meta.json next to it.
    candidate = Path(str(p) + ".meta.json")
    if candidate.is_file():
        return candidate
    return p  # fall through; _load_manifest will produce a clear error


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    manifest_path = _resolve_manifest_path(args.manifest)
    require_fields = [f.strip() for f in args.require_fields.split(",") if f.strip()]
    try:
        report = verify(manifest_path, require_fields=require_fields or None)
    except VerifyError as exc:
        if args.json:
            print(
                json.dumps(
                    {
                        "result": "FAIL",
                        "manifest_path": str(manifest_path),
                        "reason": exc.reason,
                    }
                )
            )
        print(f"FAIL: {exc.reason}", file=sys.stderr)
        return exc.code
    if args.json:
        print(json.dumps(report))
    else:
        print(f"PASS: {manifest_path}")
        for key in (
            "schema_version",
            "encryption",
            "git_sha",
            "git_describe",
            "postgres_version",
            "alembic_revision",
        ):
            value = report.get(key)
            if value:
                print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
