from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///casino_bot.db"

    class Config:
        env_file = ".env"


settings = Settings()
