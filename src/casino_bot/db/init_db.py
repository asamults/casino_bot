import casino_bot.admin.models  # noqa: F401
import casino_bot.db.models  # noqa: F401
from casino_bot.db.base import Base
from casino_bot.db.session import engine


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
