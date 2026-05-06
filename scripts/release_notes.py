from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def extract_version_notes(changelog_text: str, version: str) -> str:
    # Accept "v0.2.0" and "0.2.0".
    v = version.lstrip("v").strip()
    header_re = re.compile(
        rf"^##\s+{re.escape(v)}\s+-\s+\d{{4}}-\d{{2}}-\d{{2}}\s*$", re.M
    )
    m = header_re.search(changelog_text)
    if not m:
        raise ValueError(f"Version {v!r} not found in CHANGELOG.md")

    start = m.end()
    # Next "## " section starts the next release.
    next_m = re.compile(r"^##\s+", re.M).search(changelog_text, pos=start)
    body = changelog_text[
        start : (next_m.start() if next_m else len(changelog_text))
    ].strip()
    if not body:
        return f"Release {v}"
    return body


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Extract release notes for a version from CHANGELOG.md"
    )
    p.add_argument("--version", required=True, help="Version (e.g. v0.2.0 or 0.2.0)")
    p.add_argument(
        "--changelog",
        default="CHANGELOG.md",
        help="Path to CHANGELOG.md (default: CHANGELOG.md)",
    )
    args = p.parse_args(argv)

    text = Path(args.changelog).read_text(encoding="utf-8")
    try:
        notes = extract_version_notes(text, args.version)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(notes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
