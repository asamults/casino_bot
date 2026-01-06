import pytest

from casino_bot.compliance.constraints import (
    forbid_negative_balance,
    ComplianceViolation,
)


def test_negative_balance_forbidden():
    with pytest.raises(ComplianceViolation):
        forbid_negative_balance(balance=0, delta=-1)
