"""Synthetic-fixture tests for scripts/ops/backup_retention.sh (M5W4).

These tests exercise the retention policy with a deterministic set of
synthetic files (no Docker, no real backups). The script is invoked via
subprocess so we test the actual code path operators run, not a
re-implementation.

Layout per scenario:
- For each "day-offset" in DAYS, create three files in BACKUP_DIR:
      casino_bot_<utc>.dump.age
      casino_bot_<utc>.dump.age.sha256
      casino_bot_<utc>.dump.age.meta.json
  with mtime set to <now - day-offset> via os.utime().

Policy under test (defaults): daily=7, weekly=4, monthly=3.
"""

from __future__ import annotations

import datetime as dt
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "ops" / "backup_retention.sh"


def _make_artifact_at(backup_dir: Path, when: dt.datetime) -> tuple[str, list[Path]]:
    """Create a synthetic backup + sidecars whose mtime is set to `when`.

    Returns (basename, list_of_paths).
    """
    ts = when.strftime("%Y%m%dT%H%M%SZ")
    base = f"casino_bot_{ts}.dump.age"
    paths = [
        backup_dir / base,
        backup_dir / (base + ".sha256"),
        backup_dir / (base + ".meta.json"),
    ]
    for p in paths:
        p.write_bytes(b"")
        os.utime(p, (when.timestamp(), when.timestamp()))
    return base, paths


def _make_artifact(backup_dir: Path, day_offset: int) -> tuple[str, list[Path]]:
    """Convenience wrapper: artifact at (now - day_offset days)."""
    now = dt.datetime.now(tz=dt.timezone.utc)
    return _make_artifact_at(backup_dir, now - dt.timedelta(days=day_offset))


def _run_script(
    backup_dir: Path, *, apply: bool = False
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["BACKUP_DIR"] = str(backup_dir)
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
def backup_dir(tmp_path: Path) -> Path:
    d = tmp_path / "backups"
    d.mkdir()
    return d


def test_empty_dir_is_noop(backup_dir: Path) -> None:
    cp = _run_script(backup_dir)
    assert cp.returncode == 0, cp.stderr
    assert "no encrypted artifacts found" in cp.stdout


def test_dry_run_keeps_recent_and_lists_old_for_deletion(backup_dir: Path) -> None:
    # 8 daily-window backups (0..7 days back) + 4 older that will be
    # outside daily/weekly/monthly buckets given default policy.
    for d in range(8):
        _make_artifact(backup_dir, d)
    for d in (45, 60, 75, 90):
        _make_artifact(backup_dir, d)

    cp = _run_script(backup_dir, apply=False)
    assert cp.returncode == 0, cp.stderr

    # All 12 originals are still on disk after a dry-run.
    on_disk = {p.name for p in backup_dir.iterdir() if p.suffix == ".age"}
    assert len(on_disk) == 12, sorted(on_disk)

    # The plan must clearly partition into KEEP and DELETE sections.
    assert "--- KEEP ---" in cp.stdout
    assert "--- DELETE ---" in cp.stdout


def test_apply_deletes_loser_in_a_shared_bucket(backup_dir: Path) -> None:
    """Two backups that fall into the same OLD ISO-week and same OLD
    calendar-month: only the newer wins both buckets, the older must be
    deleted. This is the only way to force a deletion under the
    7-daily / 4-weekly / 3-monthly default policy with a small fixture.
    """
    # 7 daily-window backups (days 0..6). They occupy the last 7 dates and
    # also win the last 1-2 ISO weeks and last 1 calendar month, leaving
    # weekly slots 2..4 and monthly slots 2..3 free for older buckets.
    for d in range(7):
        _make_artifact(backup_dir, d)

    # Pick two synthetic dates that are deterministically in the same
    # ISO week and calendar month, regardless of when the test runs.
    # Anchor: the Wednesday of an old, fixed week (~3 months back),
    # plus the Tuesday of the same week. Both deep inside that week,
    # no Mon/Sun boundary risk.
    now = dt.datetime.now(tz=dt.timezone.utc)
    anchor = now - dt.timedelta(days=90)
    # Move back to the most recent Wednesday before `anchor`.
    while anchor.isoweekday() != 3:  # 1=Mon..7=Sun, 3=Wed
        anchor -= dt.timedelta(days=1)
    winner_when = anchor  # Wed
    loser_when = anchor - dt.timedelta(days=1)  # Tue (same ISO week, same month)
    assert winner_when.isocalendar()[:2] == loser_when.isocalendar()[:2], (
        winner_when,
        loser_when,
    )
    assert (winner_when.year, winner_when.month) == (loser_when.year, loser_when.month)

    _, winner_paths = _make_artifact_at(backup_dir, winner_when)
    _, loser_paths = _make_artifact_at(backup_dir, loser_when)

    cp = _run_script(backup_dir, apply=True)
    assert cp.returncode == 0, cp.stderr

    # Older of the two same-bucket backups must be deleted (with sidecars).
    for p in loser_paths:
        assert not p.exists(), f"unexpected survivor: {p}"

    # Newer of the two same-bucket backups survives (won weekly+monthly).
    for p in winner_paths:
        assert p.exists(), f"missing expected keeper: {p}"

    # Daily-7 winners survive with their sidecars.
    survivors = sorted(p.name for p in backup_dir.iterdir() if p.suffix == ".age")
    assert len(survivors) == 8, survivors  # 7 daily + 1 weekly/monthly winner
    for survivor in survivors:
        assert (backup_dir / (survivor + ".sha256")).exists()
        assert (backup_dir / (survivor + ".meta.json")).exists()


def test_apply_is_idempotent(backup_dir: Path) -> None:
    for d in range(5):
        _make_artifact(backup_dir, d)
    cp1 = _run_script(backup_dir, apply=True)
    cp2 = _run_script(backup_dir, apply=True)
    assert cp1.returncode == 0
    assert cp2.returncode == 0
    # Second run must not delete anything.
    assert "deleted 0 files" in cp2.stdout


def test_invalid_apply_value_fails(
    backup_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = os.environ.copy()
    env["BACKUP_DIR"] = str(backup_dir)
    env["APPLY"] = "maybe"
    cp = subprocess.run(
        [str(SCRIPT)],
        env=env,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert cp.returncode == 2, cp.stderr
    assert "APPLY must be" in cp.stderr


def test_missing_backup_dir_fails(tmp_path: Path) -> None:
    bogus = tmp_path / "does-not-exist"
    cp = _run_script(bogus)
    assert cp.returncode == 2, cp.stderr
    assert "BACKUP_DIR not a directory" in cp.stderr


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")
def test_script_is_executable() -> None:
    assert os.access(SCRIPT, os.X_OK), f"{SCRIPT} must be executable"
