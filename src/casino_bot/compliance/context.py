"""Inputs for compliance checks (plain dataclass, no framework deps)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ComplianceContext:
    """Snapshot passed into operation validators."""

    balance: float
    delta: float
    pending_transfer: bool = False
    pending_cash_out: bool = False
