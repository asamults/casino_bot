"""Domain ORM models (examples + tokens + users + subscriptions).

The ``examples`` table is a legacy helper sample only; no business logic.
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from casino_bot.db.base import Base


class Example(Base):
    """Legacy sample table; not part of the product domain."""

    __tablename__ = "examples"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)


class User(Base):
    """End-user identity; channel IDs are unique when set.

    ``whatsapp_phone_e164`` must be full E.164 including leading ``+`` (e.g. ``+447700900123``).
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    is_active = Column(Boolean, nullable=False, default=True)
    internal_note = Column(String(512), nullable=True)
    telegram_user_id = Column(BigInteger, unique=True, nullable=True, index=True)
    whatsapp_phone_e164 = Column(String(32), unique=True, nullable=True, index=True)
    billing_customer_id = Column(String(255), nullable=True, index=True)

    token_account = relationship(
        "TokenAccount",
        back_populates="user",
        uselist=False,
    )
    subscriptions = relationship("Subscription", back_populates="user")


class Subscription(Base):
    """Subscription row; provider webhooks (e.g. Stripe) will update status later."""

    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider = Column(String(64), nullable=False)
    external_subscription_id = Column(String(255), nullable=True)
    provider_customer_id = Column(String(255), nullable=True, index=True)
    provider_subscription_id = Column(String(255), nullable=True, index=True)
    status = Column(String(32), nullable=False)
    plan_code = Column(String(64), nullable=False)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    entitlement_active = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_subscription_id",
            name="uq_subscriptions_provider_provider_subscription_id",
        ),
    )

    user = relationship("User", back_populates="subscriptions")


class BillingWebhookEvent(Base):
    __tablename__ = "billing_webhook_events"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "external_event_id",
            name="uq_billing_webhook_events_provider_event_id",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(32), nullable=False, index=True)
    external_event_id = Column(String(255), nullable=False)
    event_type = Column(String(128), nullable=False)
    payload_hash = Column(String(128), nullable=True)
    received_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    processed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(
        String(32),
        nullable=False,
        default="received",
        server_default="received",
        index=True,
    )
    error_message = Column(String(512), nullable=True)
    raw_payload = Column(JSON, nullable=True)
    attempts_count = Column(Integer, nullable=False, default=0, server_default="0")
    dead_letter = Column(
        Boolean, nullable=False, default=False, server_default="false", index=True
    )
    last_replayed_at = Column(DateTime(timezone=True), nullable=True)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True, index=True)
    last_error_code = Column(String(64), nullable=True)
    last_error_message = Column(String(512), nullable=True)


class TokenAccount(Base):
    __tablename__ = "token_accounts"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    balance = Column(Float, nullable=False, default=0)

    user = relationship("User", back_populates="token_account")


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    delta = Column(Float, nullable=False)
    reason = Column(String(255), nullable=False)


class GameRound(Base):
    """Single-user game round record used for idempotency and audit/debug.

    Phase 1 uses a composite unique key (user_id, game_id, idempotency_key) so
    the same idempotency key can be safely reused across different games, while
    still preventing double-spend within a specific game surface.
    """

    __tablename__ = "game_rounds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    round_id = Column(String(36), nullable=False, unique=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    game_id = Column(String(128), nullable=False, index=True)
    idempotency_key = Column(String(128), nullable=False)
    bet_amount = Column(Float, nullable=False)
    payout_delta = Column(Float, nullable=False)
    status = Column(String(16), nullable=False, index=True)  # committed|rejected|failed
    details_json = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    committed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "game_id",
            "idempotency_key",
            name="uq_game_rounds_user_game_idempotency_key",
        ),
        CheckConstraint(
            "bet_amount >= 0", name="ck_game_rounds_bet_amount_non_negative"
        ),
        Index("ix_game_rounds_user_id_created_at", "user_id", "created_at"),
        Index("ix_game_rounds_game_id_created_at", "game_id", "created_at"),
    )
