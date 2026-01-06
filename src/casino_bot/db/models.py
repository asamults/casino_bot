import enum
from sqlalchemy import String, DateTime, Integer, Enum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from casino_bot.db.base import Base


class TokenType(str, enum.Enum):
    ACCESS = "access"
    CONSUMPTION = "consumption"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)


class TokenAccount(Base):
    __tablename__ = "token_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int]
    token_type: Mapped[TokenType]
    balance: Mapped[int] = mapped_column(Integer, default=0)


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int]
    delta: Mapped[int]
    reason: Mapped[str]
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
