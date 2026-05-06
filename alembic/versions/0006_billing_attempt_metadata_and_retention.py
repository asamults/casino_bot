"""Billing webhook attempt metadata and retention support.

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "billing_webhook_events",
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "billing_webhook_events",
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "billing_webhook_events",
        sa.Column("last_error_message", sa.String(length=512), nullable=True),
    )
    op.create_index(
        "ix_billing_webhook_events_last_attempt_at",
        "billing_webhook_events",
        ["last_attempt_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_billing_webhook_events_last_attempt_at", table_name="billing_webhook_events"
    )
    op.drop_column("billing_webhook_events", "last_error_message")
    op.drop_column("billing_webhook_events", "last_error_code")
    op.drop_column("billing_webhook_events", "last_attempt_at")
