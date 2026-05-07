"""Synthetic-fixture tests for scripts/ops/evidence_retention.sh (M5W4/M6W4).

Goals:
- Ensure the default is dry-run (no deletions/moves).
- Ensure APPLY=true performs deterministic archive/delete actions.
- Ensure the dry-run plan output is deterministic for a fixed fixture.

No Docker; uses subprocess to exercise the real operator entrypoint.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "ops" / "evidence_retention.sh"


def _write_report(path: Path, *, result: str) -> None:
    path.write_text(
        json.dumps({"result": result, "backup_file": "x"}), encoding="utf-8"
    )
    # Force deterministic mtimes so "newest KEEP_LAST" is predictable.
    # Use ascending integers as epoch seconds.
    epoch = int(path.stem.replace("t", "").replace("z", ""))  # e.g. "1", "2", "3"
    os.utime(path, (epoch, epoch))


def _run(
    report_dir: Path, *, keep_last: int = 2, apply: bool = False
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["REPORT_DIR"] = str(report_dir)
    env["KEEP_LAST"] = str(keep_last)
    if apply:
        env["APPLY"] = "true"
    return subprocess.run(
        [str(SCRIPT)],
        env=env,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def report_dir(tmp_path: Path) -> Path:
    d = tmp_path / "reports"
    d.mkdir()
    return d


def test_default_is_dry_run_no_mutations(report_dir: Path) -> None:
    _write_report(report_dir / "1.json", result="PASS")
    _write_report(report_dir / "2.json", result="PASS")
    _write_report(report_dir / "3.json", result="FAIL")

    cp = _run(report_dir, keep_last=1, apply=False)
    assert cp.returncode == 0, cp.stderr
    assert "(dry-run)" in cp.stdout

    # No archive dir should be created by a dry-run (but it's ok if it is);
    # more importantly, original files must still exist.
    assert (report_dir / "1.json").exists()
    assert (report_dir / "2.json").exists()
    assert (report_dir / "3.json").exists()


def test_apply_archives_nonpass_and_deletes_old_pass(report_dir: Path) -> None:
    # PASS newest: 2.json, older: 1.json. Non-PASS: 3.json.
    _write_report(report_dir / "1.json", result="PASS")
    _write_report(report_dir / "2.json", result="PASS")
    _write_report(report_dir / "3.json", result="FAIL")

    cp = _run(report_dir, keep_last=1, apply=True)
    assert cp.returncode == 0, cp.stderr
    assert "PASS: deleted=" in cp.stdout

    # Keep newest PASS.
    assert (report_dir / "2.json").exists()
    # Delete older PASS.
    assert not (report_dir / "1.json").exists()
    # Archive FAIL.
    assert (report_dir / "archive" / "3.json").exists()


def test_plan_output_is_deterministic(report_dir: Path) -> None:
    _write_report(report_dir / "1.json", result="PASS")
    _write_report(report_dir / "2.json", result="PASS")
    _write_report(report_dir / "3.json", result="FAIL")

    cp1 = _run(report_dir, keep_last=1, apply=False)
    cp2 = _run(report_dir, keep_last=1, apply=False)
    assert cp1.returncode == 0, cp1.stderr
    assert cp2.returncode == 0, cp2.stderr
    assert cp1.stdout == cp2.stdout


def test_script_is_executable() -> None:
    assert os.access(SCRIPT, os.X_OK), f"{SCRIPT} must be executable"
