"""Phase 7 — integer token_units on accounts and ledger.

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

# Must match Settings.TOKEN_UNIT_SCALE default until env-driven migrations exist.
_SCALE = 1000


def upgrade() -> None:
    op.add_column(
        "token_accounts",
        sa.Column(
            "balance_units",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
    )
    op.execute(
        f"UPDATE token_accounts SET balance_units = "
        f"CAST(ROUND(balance * {_SCALE}) AS BIGINT)"
    )

    op.add_column(
        "ledger_entries",
        sa.Column("delta_units", sa.BigInteger(), nullable=True),
    )
    op.execute(
        f"UPDATE ledger_entries SET delta_units = "
        f"CAST(ROUND(delta * {_SCALE}) AS BIGINT)"
    )
    op.alter_column(
        "ledger_entries",
        "delta_units",
        existing_type=sa.BigInteger(),
        nullable=False,
        server_default="0",
    )

    op.add_column(
        "game_rounds",
        sa.Column(
            "bet_units",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "game_rounds",
        sa.Column(
            "payout_units",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
    )
    op.execute(
        f"UPDATE game_rounds SET bet_units = CAST(ROUND(bet_amount * {_SCALE}) AS BIGINT), "
        f"payout_units = CAST(ROUND(payout_delta * {_SCALE}) AS BIGINT)"
    )


def downgrade() -> None:
    op.drop_column("game_rounds", "payout_units")
    op.drop_column("game_rounds", "bet_units")
    op.drop_column("ledger_entries", "delta_units")
    op.drop_column("token_accounts", "balance_units")
