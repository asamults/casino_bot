"""Domain users, subscriptions, FKs to users, audit details JSON.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-04

Upgrade: creates ``users``, backfills rows for existing ``token_accounts`` /
``ledger_entries`` ``user_id`` values, adds ``subscriptions``, foreign keys,
and ``audit_logs.details``. Downgrade removes these in reverse order.
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("TIMEZONE('utc', now())"),
            nullable=False,
        ),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("internal_note", sa.String(512), nullable=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
        sa.Column("whatsapp_phone_e164", sa.String(32), nullable=True),
        sa.Column("billing_customer_id", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_users_telegram_user_id",
        "users",
        ["telegram_user_id"],
        unique=True,
    )
    op.create_index(
        "ix_users_whatsapp_phone_e164",
        "users",
        ["whatsapp_phone_e164"],
        unique=True,
    )
    op.create_index("ix_users_billing_customer_id", "users", ["billing_customer_id"])

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            INSERT INTO users (id, created_at, is_active)
            SELECT DISTINCT uid, TIMEZONE('utc', now()), true
            FROM (
                SELECT user_id AS uid FROM token_accounts
                UNION
                SELECT user_id FROM ledger_entries
            ) AS uids
            WHERE uid IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM users usr WHERE usr.id = uid)
            """
        )
    )
    mx = bind.execute(sa.text("SELECT COALESCE(MAX(id), 0) FROM users")).scalar()
    if mx == 0:
        bind.execute(
            sa.text("SELECT setval(pg_get_serial_sequence('users', 'id'), 1, false)")
        )
    else:
        bind.execute(
            sa.text("SELECT setval(pg_get_serial_sequence('users', 'id'), :mx, true)"),
            {"mx": mx},
        )

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("external_subscription_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("plan_code", sa.String(64), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("TIMEZONE('utc', now())"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("TIMEZONE('utc', now())"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])

    op.create_foreign_key(
        "fk_token_accounts_user_id_users",
        "token_accounts",
        "users",
        ["user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_ledger_entries_user_id_users",
        "ledger_entries",
        "users",
        ["user_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.add_column(
        "audit_logs",
        sa.Column("details", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("audit_logs", "details")

    op.drop_constraint(
        "fk_ledger_entries_user_id_users", "ledger_entries", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_token_accounts_user_id_users", "token_accounts", type_="foreignkey"
    )

    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_table("subscriptions")

    op.drop_index("ix_users_billing_customer_id", table_name="users")
    op.drop_index("ix_users_whatsapp_phone_e164", table_name="users")
    op.drop_index("ix_users_telegram_user_id", table_name="users")
    op.drop_table("users")
