from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "casino_bot"
    ENV: str = "dev"

    DATABASE_URL: str = "sqlite:///./casino_bot.db"

    class Config:
        env_file = ".env"
        frozen = True


settings = Settings()
