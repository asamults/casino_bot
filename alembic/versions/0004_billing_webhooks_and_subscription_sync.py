"""Billing webhook idempotency table and subscription sync fields.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "billing_webhook_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("external_event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("payload_hash", sa.String(length=128), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("TIMEZONE('utc', now())"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'received'"),
        ),
        sa.Column("error_message", sa.String(length=512), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "external_event_id",
            name="uq_billing_webhook_events_provider_event_id",
        ),
    )
    op.create_index(
        "ix_billing_webhook_events_provider", "billing_webhook_events", ["provider"]
    )
    op.create_index(
        "ix_billing_webhook_events_status", "billing_webhook_events", ["status"]
    )
    op.create_index(
        "ix_billing_webhook_events_received_at",
        "billing_webhook_events",
        ["received_at"],
    )

    op.add_column(
        "subscriptions",
        sa.Column("provider_customer_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("provider_subscription_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column(
            "cancel_at_period_end",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "subscriptions",
        sa.Column(
            "entitlement_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index(
        "ix_subscriptions_provider_customer_id",
        "subscriptions",
        ["provider_customer_id"],
    )
    op.create_index(
        "ix_subscriptions_provider_subscription_id",
        "subscriptions",
        ["provider_subscription_id"],
    )
    op.create_unique_constraint(
        "uq_subscriptions_provider_provider_subscription_id",
        "subscriptions",
        ["provider", "provider_subscription_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_subscriptions_provider_provider_subscription_id",
        "subscriptions",
        type_="unique",
    )
    op.drop_index(
        "ix_subscriptions_provider_subscription_id", table_name="subscriptions"
    )
    op.drop_index("ix_subscriptions_provider_customer_id", table_name="subscriptions")
    op.drop_column("subscriptions", "entitlement_active")
    op.drop_column("subscriptions", "cancel_at_period_end")
    op.drop_column("subscriptions", "provider_subscription_id")
    op.drop_column("subscriptions", "provider_customer_id")

    op.drop_index(
        "ix_billing_webhook_events_received_at", table_name="billing_webhook_events"
    )
    op.drop_index(
        "ix_billing_webhook_events_status", table_name="billing_webhook_events"
    )
    op.drop_index(
        "ix_billing_webhook_events_provider", table_name="billing_webhook_events"
    )
    op.drop_table("billing_webhook_events")
