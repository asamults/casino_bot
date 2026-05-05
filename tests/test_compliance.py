import pytest

from casino_bot.compliance.context import ComplianceContext
from casino_bot.compliance.constraints import (
    ComplianceViolation,
    forbid_negative_balance,
)
from casino_bot.compliance.registry import Operation, validate_operation


def test_negative_balance_forbidden_legacy_helper():
    with pytest.raises(ComplianceViolation):
        forbid_negative_balance(balance=0, delta=-1)


def test_token_debit_negative_balance():
    with pytest.raises(ComplianceViolation):
        validate_operation(
            Operation.TOKEN_DEBIT,
            ComplianceContext(balance=1.0, delta=-2.0),
        )


def test_token_debit_success():
    validate_operation(
        Operation.TOKEN_DEBIT,
        ComplianceContext(balance=5.0, delta=-1.0),
    )


def test_token_debit_blocked_pending_cash_out():
    with pytest.raises(ComplianceViolation, match="cash-out"):
        validate_operation(
            Operation.TOKEN_DEBIT,
            ComplianceContext(
                balance=10.0,
                delta=-1.0,
                pending_cash_out=True,
            ),
        )


def test_token_debit_blocked_pending_transfer():
    with pytest.raises(ComplianceViolation, match="transfer"):
        validate_operation(
            Operation.TOKEN_DEBIT,
            ComplianceContext(
                balance=10.0,
                delta=-1.0,
                pending_transfer=True,
            ),
        )


def test_token_credit_blocked_pending_cash_out():
    with pytest.raises(ComplianceViolation, match="cash-out"):
        validate_operation(
            Operation.TOKEN_CREDIT,
            ComplianceContext(
                balance=0.0,
                delta=5.0,
                pending_cash_out=True,
            ),
        )


def test_token_credit_blocked_pending_transfer():
    with pytest.raises(ComplianceViolation, match="transfer"):
        validate_operation(
            Operation.TOKEN_CREDIT,
            ComplianceContext(
                balance=0.0,
                delta=5.0,
                pending_transfer=True,
            ),
        )


def test_token_credit_ok():
    validate_operation(
        Operation.TOKEN_CREDIT,
        ComplianceContext(balance=0.0, delta=3.0),
    )


def test_transfer_prohibited():
    with pytest.raises(ComplianceViolation, match="prohibited"):
        validate_operation(
            Operation.TRANSFER,
            ComplianceContext(balance=0.0, delta=0.0),
        )


def test_transfer_duplicate_pending():
    with pytest.raises(ComplianceViolation, match="already pending"):
        validate_operation(
            Operation.TRANSFER,
            ComplianceContext(
                balance=0.0,
                delta=0.0,
                pending_transfer=True,
            ),
        )


def test_cash_out_prohibited():
    with pytest.raises(ComplianceViolation, match="prohibited"):
        validate_operation(
            Operation.CASH_OUT,
            ComplianceContext(balance=0.0, delta=0.0),
        )


def test_cash_out_duplicate_pending():
    with pytest.raises(ComplianceViolation, match="already pending"):
        validate_operation(
            Operation.CASH_OUT,
            ComplianceContext(
                balance=0.0,
                delta=0.0,
                pending_cash_out=True,
            ),
        )
