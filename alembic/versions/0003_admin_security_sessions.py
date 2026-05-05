"""Admin sessions, login locks, and timezone fixes for admin tables.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("admin_users", "created_at", type_=sa.DateTime(timezone=True))
    op.alter_column("audit_logs", "created_at", type_=sa.DateTime(timezone=True))

    op.create_table(
        "admin_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("admin_user_id", sa.Integer(), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=128), nullable=False),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("TIMEZONE('utc', now())"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rotated_from_session_id", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(
            ["admin_user_id"], ["admin_users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["rotated_from_session_id"],
            ["admin_sessions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_admin_sessions_admin_user_id", "admin_sessions", ["admin_user_id"]
    )
    op.create_index("ix_admin_sessions_expires_at", "admin_sessions", ["expires_at"])
    op.create_index("ix_admin_sessions_revoked_at", "admin_sessions", ["revoked_at"])
    op.create_index(
        "ix_admin_sessions_rotated_from_session_id",
        "admin_sessions",
        ["rotated_from_session_id"],
    )
    op.create_index(
        "ix_admin_sessions_refresh_token_hash",
        "admin_sessions",
        ["refresh_token_hash"],
        unique=True,
    )

    op.create_table(
        "admin_login_locks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("identity", sa.String(length=255), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=False),
        sa.Column(
            "attempts_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "first_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("TIMEZONE('utc', now())"),
            nullable=False,
        ),
        sa.Column(
            "last_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("TIMEZONE('utc', now())"),
            nullable=False,
        ),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_login_locks_identity", "admin_login_locks", ["identity"])
    op.create_index(
        "ix_admin_login_locks_ip_address", "admin_login_locks", ["ip_address"]
    )
    op.create_index(
        "ix_admin_login_locks_locked_until", "admin_login_locks", ["locked_until"]
    )


def downgrade() -> None:
    op.drop_index("ix_admin_login_locks_locked_until", table_name="admin_login_locks")
    op.drop_index("ix_admin_login_locks_ip_address", table_name="admin_login_locks")
    op.drop_index("ix_admin_login_locks_identity", table_name="admin_login_locks")
    op.drop_table("admin_login_locks")

    op.drop_index("ix_admin_sessions_refresh_token_hash", table_name="admin_sessions")
    op.drop_index(
        "ix_admin_sessions_rotated_from_session_id", table_name="admin_sessions"
    )
    op.drop_index("ix_admin_sessions_revoked_at", table_name="admin_sessions")
    op.drop_index("ix_admin_sessions_expires_at", table_name="admin_sessions")
    op.drop_index("ix_admin_sessions_admin_user_id", table_name="admin_sessions")
    op.drop_table("admin_sessions")

    op.alter_column("audit_logs", "created_at", type_=sa.DateTime(timezone=False))
    op.alter_column("admin_users", "created_at", type_=sa.DateTime(timezone=False))
