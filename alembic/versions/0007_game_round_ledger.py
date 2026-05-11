"""Game rounds table for idempotent round ledger (Phase 1).

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game_rounds",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("round_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("bet_amount", sa.Float(), nullable=False),
        sa.Column("payout_delta", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("bet_amount >= 0", name="ck_game_rounds_bet_amount_non_negative"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_game_rounds_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("round_id", name="uq_game_rounds_round_id"),
        sa.UniqueConstraint(
            "user_id",
            "game_id",
            "idempotency_key",
            name="uq_game_rounds_user_game_idempotency_key",
        ),
    )

    op.create_index("ix_game_rounds_user_id", "game_rounds", ["user_id"])
    op.create_index("ix_game_rounds_game_id", "game_rounds", ["game_id"])
    op.create_index("ix_game_rounds_status", "game_rounds", ["status"])
    op.create_index("ix_game_rounds_round_id", "game_rounds", ["round_id"])
    op.create_index(
        "ix_game_rounds_user_id_created_at", "game_rounds", ["user_id", "created_at"]
    )
    op.create_index(
        "ix_game_rounds_game_id_created_at", "game_rounds", ["game_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_game_rounds_game_id_created_at", table_name="game_rounds")
    op.drop_index("ix_game_rounds_user_id_created_at", table_name="game_rounds")
    op.drop_index("ix_game_rounds_round_id", table_name="game_rounds")
    op.drop_index("ix_game_rounds_status", table_name="game_rounds")
    op.drop_index("ix_game_rounds_game_id", table_name="game_rounds")
    op.drop_index("ix_game_rounds_user_id", table_name="game_rounds")
    op.drop_table("game_rounds")

