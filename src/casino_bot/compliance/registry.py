"""Operation registry: map Operation → ordered check functions."""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum

from casino_bot.compliance.context import ComplianceContext
from casino_bot.compliance.violations import ComplianceViolation


class Operation(str, Enum):
    """High-level business operations subject to compliance."""

    TOKEN_CREDIT = "token_credit"  # nosec B105
    TOKEN_DEBIT = "token_debit"  # nosec B105
    TRANSFER = "transfer"
    CASH_OUT = "cash_out"


def _negative_balance(ctx: ComplianceContext) -> None:
    if ctx.balance + ctx.delta < 0:
        raise ComplianceViolation("Operation would result in negative balance")


def _debit_blocked_pending_cash_out(ctx: ComplianceContext) -> None:
    if ctx.pending_cash_out and ctx.delta < 0:
        raise ComplianceViolation(
            "Token debits are blocked while a cash-out request is pending"
        )


def _debit_blocked_pending_transfer(ctx: ComplianceContext) -> None:
    if ctx.pending_transfer and ctx.delta < 0:
        raise ComplianceViolation(
            "Token debits are blocked while a transfer request is pending"
        )


def _credit_blocked_pending_cash_out(ctx: ComplianceContext) -> None:
    if ctx.pending_cash_out and ctx.delta > 0:
        raise ComplianceViolation(
            "Token credits are blocked while a cash-out request is pending"
        )


def _credit_blocked_pending_transfer(ctx: ComplianceContext) -> None:
    if ctx.pending_transfer and ctx.delta > 0:
        raise ComplianceViolation(
            "Token credits are blocked while a transfer request is pending"
        )


def _transfer_policy(ctx: ComplianceContext) -> None:
    if ctx.pending_transfer:
        raise ComplianceViolation("A transfer request is already pending")
    raise ComplianceViolation("Transfers between users are prohibited (non-gambling)")


def _cash_out_policy(ctx: ComplianceContext) -> None:
    if ctx.pending_cash_out:
        raise ComplianceViolation("A cash-out request is already pending")
    raise ComplianceViolation("Cash-out is prohibited (non-gambling)")


OperationCheck = Callable[[ComplianceContext], None]

REGISTRY: dict[Operation, list[OperationCheck]] = {
    Operation.TOKEN_DEBIT: [
        _negative_balance,
        _debit_blocked_pending_cash_out,
        _debit_blocked_pending_transfer,
    ],
    Operation.TOKEN_CREDIT: [
        _credit_blocked_pending_cash_out,
        _credit_blocked_pending_transfer,
    ],
    Operation.TRANSFER: [_transfer_policy],
    Operation.CASH_OUT: [_cash_out_policy],
}


def validate_operation(operation: Operation, ctx: ComplianceContext) -> None:
    """Run all registered checks for ``operation``; raise ``ComplianceViolation`` on failure."""
    for check in REGISTRY.get(operation, []):
        check(ctx)
