"""
Compliance constraints.
Non-gambling, UK legal-by-design.
"""

class ComplianceViolation(Exception):
    pass


def assert_no_cash_out(*, cash_out_enabled: bool) -> None:
    if cash_out_enabled:
        raise ComplianceViolation("Cash-out is prohibited")


def assert_no_transfer(*, transfer_enabled: bool) -> None:
    if transfer_enabled:
        raise ComplianceViolation("Transfers between users are prohibited")

"""

def forbid_negative_balance(*, balance: int | float) -> None:
    '''
    Enforces invariant: user balance must be non-negative.
    '''
    if balance < 0:
        raise ComplianceViolation("Negative balance is forbidden")

"""


def forbid_negative_balance(balance: float, delta: float):
    if balance + delta < 0:
        raise ComplianceViolation("Operation would result in negative balance")