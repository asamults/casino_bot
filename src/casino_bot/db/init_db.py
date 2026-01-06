from casino_bot.db.session import engine
from casino_bot.db.base import Base
from casino_bot.db import models  # noqa: F401


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
