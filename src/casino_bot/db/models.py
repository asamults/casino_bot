from sqlalchemy import Column, Integer, String
from src.casino_bot.db.base import Base


class Example(Base):
    __tablename__ = "examples"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
