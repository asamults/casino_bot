class ComplianceViolation(Exception):
    """Raised when an operation violates non-gambling constraints."""


def forbid_token_transfer(
    from_user_id: int,
    to_user_id: int,
) -> None:
    if from_user_id != to_user_id:
        raise ComplianceViolation("Token transfer between users is forbidden.")


def forbid_cash_out() -> None:
    raise ComplianceViolation("Cash-out operations are forbidden.")


def forbid_negative_balance(balance: int, delta: int) -> None:
    if balance + delta < 0:
        raise ComplianceViolation("Negative balance is forbidden.")
