"""
Compliance constraints (non-gambling, UK legal-by-design).

Prefer ``validate_operation`` from ``casino_bot.compliance.registry`` for new code.
"""

from casino_bot.compliance.context import ComplianceContext
from casino_bot.compliance.registry import Operation, validate_operation
from casino_bot.compliance.violations import ComplianceViolation


def assert_no_cash_out(*, cash_out_enabled: bool) -> None:
    if cash_out_enabled:
        raise ComplianceViolation("Cash-out is prohibited")


def assert_no_transfer(*, transfer_enabled: bool) -> None:
    if transfer_enabled:
        raise ComplianceViolation("Transfers between users are prohibited")


def forbid_negative_balance(*, balance_units: int, delta_units: int) -> None:
    """Reject debits that would make balance negative (legacy helper)."""
    if delta_units >= 0:
        return
    validate_operation(
        Operation.TOKEN_DEBIT,
        ComplianceContext(balance_units=balance_units, delta_units=delta_units),
    )


__all__ = [
    "ComplianceViolation",
    "ComplianceContext",
    "Operation",
    "validate_operation",
    "assert_no_cash_out",
    "assert_no_transfer",
    "forbid_negative_balance",
]
