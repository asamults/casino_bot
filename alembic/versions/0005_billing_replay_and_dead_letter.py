"""Add replay/dead-letter fields for billing webhook events.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "billing_webhook_events", sa.Column("raw_payload", sa.JSON(), nullable=True)
    )
    op.add_column(
        "billing_webhook_events",
        sa.Column(
            "attempts_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
    )
    op.add_column(
        "billing_webhook_events",
        sa.Column(
            "dead_letter", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.add_column(
        "billing_webhook_events",
        sa.Column("last_replayed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_billing_webhook_events_dead_letter",
        "billing_webhook_events",
        ["dead_letter"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_billing_webhook_events_dead_letter", table_name="billing_webhook_events"
    )
    op.drop_column("billing_webhook_events", "last_replayed_at")
    op.drop_column("billing_webhook_events", "dead_letter")
    op.drop_column("billing_webhook_events", "attempts_count")
    op.drop_column("billing_webhook_events", "raw_payload")
