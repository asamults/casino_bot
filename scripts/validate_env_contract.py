from __future__ import annotations

import argparse
import sys

from casino_bot.settings import Settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate casino_bot env contract (fails fast on invalid env)."
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Env file to load (default: .env). Use .env.example in CI.",
    )
    args = parser.parse_args(argv)

    try:
        Settings(_env_file=args.env_file)
    except Exception as exc:
        print(f"ENV contract validation failed: {exc}", file=sys.stderr)
        return 2
    print("OK: env contract valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
