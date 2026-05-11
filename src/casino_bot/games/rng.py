"""Centralized RNG for games (Phase 2 — not provably fair)."""

from __future__ import annotations

import secrets

RNG_VERSION = "v1"


def new_rng() -> secrets.SystemRandom:
    """Return a new cryptographically strong RNG instance (no seeds persisted)."""
    return secrets.SystemRandom()
