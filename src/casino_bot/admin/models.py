from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import relationship

from casino_bot.db.base import Base


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), default="admin")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    actor = Column(String(255), nullable=False)
    action = Column(String(512), nullable=False)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class AdminSession(Base):
    __tablename__ = "admin_sessions"

    id = Column(String(36), primary_key=True)
    admin_user_id = Column(
        Integer,
        ForeignKey("admin_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    refresh_token_hash = Column(String(128), nullable=False, unique=True, index=True)
    user_agent = Column(String(512), nullable=True)
    ip_address = Column(String(64), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True, index=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    rotated_from_session_id = Column(
        String(36),
        ForeignKey("admin_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    admin_user = relationship("AdminUser")
    rotated_from = relationship("AdminSession", remote_side=[id], uselist=False)


class AdminLoginLock(Base):
    __tablename__ = "admin_login_locks"

    id = Column(Integer, primary_key=True)
    identity = Column(String(255), nullable=False, index=True)
    ip_address = Column(String(64), nullable=False, index=True)
    attempts_count = Column(Integer, nullable=False, default=0)
    first_attempt_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_attempt_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    locked_until = Column(DateTime(timezone=True), nullable=True, index=True)
