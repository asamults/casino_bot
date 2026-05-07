"""Synthetic-fixture tests for scripts/ops/verify_backup_manifest.py (M5W4).

These tests exercise the manifest validator directly via subprocess, so
we test the same code path operators run. No Docker or real backups
required: each test creates a tiny synthetic encrypted artifact + a
matching .meta.json + an optional .sha256 sidecar.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "ops" / "verify_backup_manifest.py"


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_artifact_set(
    dir_: Path,
    basename: str,
    payload: bytes,
    manifest_overrides: dict | None = None,
    write_sidecar: bool = True,
    schema_version: int = 2,
) -> tuple[Path, Path, Path]:
    enc_path = dir_ / basename
    sha_path = dir_ / (basename + ".sha256")
    meta_path = dir_ / (basename + ".meta.json")

    enc_path.write_bytes(payload)
    sha_hex = _sha256_hex(payload)
    if write_sidecar:
        sha_path.write_text(f"{sha_hex}  {basename}\n", encoding="utf-8")

    base = {
        "schema_version": schema_version,
        "created_at_utc": "2026-05-07T00:00:00Z",
        "tool": "age",
        "encryption": "age",
        "recipient": "age:ops/backup/age-recipients.txt",
        "plaintext_basename": basename.replace(".age", ""),
        "encrypted_basename": basename,
        "plaintext_size_bytes": 30,
        "encrypted_size_bytes": len(payload),
        "sha256": sha_hex,
        "compose_file": "docker-compose.prod.yml",
        "env_file": ".env.prod.example",
        "postgres_service": "postgres",
        "git_sha": "abc1234",
        "git_describe": "v0.0.1-1-gabc1234",
        "postgres_version": "16.11",
        "alembic_revision": "deadbeef",
    }
    if schema_version == 1:
        for k in (
            "encryption",
            "git_sha",
            "git_describe",
            "postgres_version",
            "alembic_revision",
        ):
            base.pop(k, None)
    if manifest_overrides:
        base.update(manifest_overrides)
    meta_path.write_text(json.dumps(base, indent=2), encoding="utf-8")
    return enc_path, sha_path, meta_path


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_pass_v2_full_manifest(tmp_path: Path) -> None:
    enc, _, meta = _write_artifact_set(tmp_path, "casino_bot_x.dump.age", b"hello")
    cp = _run(str(meta))
    assert cp.returncode == 0, cp.stderr
    assert cp.stdout.startswith("PASS:")


def test_pass_v1_legacy_manifest_is_accepted(tmp_path: Path) -> None:
    enc, _, meta = _write_artifact_set(
        tmp_path, "legacy.dump.age", b"hello", schema_version=1
    )
    cp = _run(str(meta))
    assert cp.returncode == 0, cp.stderr
    assert "PASS:" in cp.stdout


def test_can_pass_encrypted_path_directly(tmp_path: Path) -> None:
    enc, _, _ = _write_artifact_set(tmp_path, "x.dump.age", b"abc")
    # Pass the artifact path; verifier must infer .meta.json next to it.
    cp = _run(str(enc))
    assert cp.returncode == 0, cp.stderr
    assert "PASS:" in cp.stdout


def test_fail_unsupported_schema_version(tmp_path: Path) -> None:
    enc, _, meta = _write_artifact_set(
        tmp_path, "x.dump.age", b"abc", manifest_overrides={"schema_version": 99}
    )
    cp = _run(str(meta))
    assert cp.returncode == 3, cp.stderr
    assert "schema_version" in cp.stderr


def test_fail_missing_required_field(tmp_path: Path) -> None:
    # Build a v2 manifest then strip a required field.
    _, _, meta = _write_artifact_set(tmp_path, "x.dump.age", b"abc")
    doc = json.loads(meta.read_text())
    doc.pop("encrypted_basename")
    meta.write_text(json.dumps(doc), encoding="utf-8")
    cp = _run(str(meta))
    assert cp.returncode == 3, cp.stderr
    assert "missing required fields" in cp.stderr


def test_fail_sha256_mismatch(tmp_path: Path) -> None:
    enc, sha, meta = _write_artifact_set(tmp_path, "x.dump.age", b"abc")
    # Tamper the encrypted artifact after the manifest was written.
    enc.write_bytes(b"tampered")
    cp = _run(str(meta))
    assert cp.returncode == 3, cp.stderr
    assert "sha256 mismatch" in cp.stderr


def test_fail_sidecar_disagrees_with_manifest(tmp_path: Path) -> None:
    enc, sha, meta = _write_artifact_set(tmp_path, "x.dump.age", b"abc")
    sha.write_text(
        "0000000000000000000000000000000000000000000000000000000000000000  x.dump.age\n"
    )
    cp = _run(str(meta))
    assert cp.returncode == 3, cp.stderr
    assert "sha256 sidecar disagrees" in cp.stderr


def test_fail_missing_encrypted_artifact(tmp_path: Path) -> None:
    enc, _, meta = _write_artifact_set(tmp_path, "x.dump.age", b"abc")
    enc.unlink()
    cp = _run(str(meta))
    assert cp.returncode == 2, cp.stderr
    assert "encrypted artifact not found" in cp.stderr


def test_v2_allows_empty_provenance_fields_by_default(tmp_path: Path) -> None:
    # Hosts that can't query postgres at backup time emit empty
    # postgres_version / alembic_revision; verifier accepts that.
    _, _, meta = _write_artifact_set(
        tmp_path,
        "x.dump.age",
        b"abc",
        manifest_overrides={
            "git_sha": "",
            "git_describe": "",
            "postgres_version": "",
            "alembic_revision": "",
        },
    )
    cp = _run(str(meta))
    assert cp.returncode == 0, cp.stderr


def test_require_fields_can_force_provenance(tmp_path: Path) -> None:
    _, _, meta = _write_artifact_set(
        tmp_path,
        "x.dump.age",
        b"abc",
        manifest_overrides={"git_sha": "", "alembic_revision": ""},
    )
    cp = _run(
        str(meta),
        "--require-fields",
        "git_sha,alembic_revision",
    )
    assert cp.returncode == 3, cp.stderr
    assert "git_sha" in cp.stderr
    assert "alembic_revision" in cp.stderr


def test_json_output_pass(tmp_path: Path) -> None:
    enc, _, meta = _write_artifact_set(tmp_path, "x.dump.age", b"abc")
    cp = _run(str(meta), "--json")
    assert cp.returncode == 0, cp.stderr
    payload = json.loads(cp.stdout.splitlines()[-1])
    assert payload["result"] == "PASS"
    assert payload["schema_version"] == 2
    assert payload["sha256_verified"] == _sha256_hex(b"abc")


def test_json_output_fail(tmp_path: Path) -> None:
    _, _, meta = _write_artifact_set(tmp_path, "x.dump.age", b"abc")
    doc = json.loads(meta.read_text())
    doc["sha256"] = "0" * 64
    meta.write_text(json.dumps(doc), encoding="utf-8")
    cp = _run(str(meta), "--json")
    assert cp.returncode == 3, cp.stderr
    payload = json.loads(cp.stdout.splitlines()[-1])
    assert payload["result"] == "FAIL"
    assert "sha256 mismatch" in payload["reason"]


def test_script_is_executable() -> None:
    assert os.access(SCRIPT, os.X_OK), f"{SCRIPT} must be executable"
