"""Application configuration (single source of truth)."""

from __future__ import annotations

from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_DATABASE_URL = "postgresql+psycopg://casino:secret@localhost:5432/casino_db"
DEV_SECRET_KEY = "DEV_ONLY_CHANGE_ME"
DEV_REFRESH_PEPPER = "DEV_REFRESH_PEPPER_CHANGE_ME"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str = DEV_DATABASE_URL
    SECRET_KEY: str = DEV_SECRET_KEY
    JWT_SIGNING_KEY: str = DEV_SECRET_KEY
    REFRESH_TOKEN_PEPPER: str = DEV_REFRESH_PEPPER

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    MAX_LOGIN_ATTEMPTS: int = 5
    ATTEMPT_WINDOW_SECONDS: int = 300
    LOCKOUT_SECONDS: int = 900

    LOGIN_RATE_LIMIT_PER_MINUTE: int = 5
    REFRESH_RATE_LIMIT_PER_MINUTE: int = 30
    READ_RATE_LIMIT_PER_MINUTE: int = 120
    WRITE_RATE_LIMIT_PER_MINUTE: int = 30

    CORS_ALLOW_ORIGINS: list[str] = []
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"]
    CORS_ALLOW_HEADERS: list[str] = ["Authorization", "Content-Type", "X-Request-ID"]
    ALLOWED_HOSTS: list[str] = ["localhost", "127.0.0.1"]
    BILLING_PROVIDER_PRIMARY: Literal["stripe", "paddle"] = "stripe"
    BILLING_ENABLE_WEBHOOKS: bool = False
    BILLING_ENABLE_CHECKOUT: bool = False
    BILLING_FAIL_ON_MISSING_SECRETS_IN_PROD: bool = True
    STRIPE_WEBHOOK_SECRET: str = ""
    PADDLE_WEBHOOK_SECRET: str = ""
    STRIPE_API_KEY: str = ""
    PADDLE_API_KEY: str = ""
    BILLING_ALLOWED_PLANS: list[str] = ["test_plan", "pro_monthly"]
    BILLING_ALLOWED_RETURN_HOSTS: list[str] = ["localhost", "127.0.0.1"]
    BILLING_WEBHOOK_TOLERANCE_SECONDS: int = 300
    BILLING_DEAD_LETTER_ATTEMPTS: int = 5
    BILLING_WEBHOOK_RETENTION_DAYS: int = 90
    BILLING_POLICY_TOS_URL: str = ""
    BILLING_POLICY_REFUND_URL: str = ""
    BILLING_POLICY_CANCELLATION_URL: str = ""
    USER_API_INTERNAL_TOKEN: str = "dev-user-api-token"
    ENTITLEMENT_GRACE_SECONDS: int = 0
    ENTITLEMENT_ENFORCEMENT_MODE: Literal["soft", "hard"] = "hard"

    @field_validator(
        "SECRET_KEY", "DATABASE_URL", "JWT_SIGNING_KEY", "REFRESH_TOKEN_PEPPER"
    )
    @classmethod
    def strip_strings(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v

    @field_validator("CORS_ALLOW_ORIGINS", mode="before")
    @classmethod
    def split_csv_origins(cls, value):
        if isinstance(value, str):
            raw = [item.strip() for item in value.split(",")]
            return [item for item in raw if item]
        return value

    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def split_csv_hosts(cls, value):
        if isinstance(value, str):
            raw = [item.strip() for item in value.split(",")]
            return [item for item in raw if item]
        return value

    @field_validator(
        "BILLING_ALLOWED_PLANS", "BILLING_ALLOWED_RETURN_HOSTS", mode="before"
    )
    @classmethod
    def split_csv_lists(cls, value):
        if isinstance(value, str):
            raw = [item.strip() for item in value.split(",")]
            return [item for item in raw if item]
        return value

    @model_validator(mode="after")
    def validate_production_secrets(self) -> Settings:
        if self.ENVIRONMENT != "production":
            return self
        errors: list[str] = []
        if not self.SECRET_KEY or self.SECRET_KEY == DEV_SECRET_KEY:
            errors.append(
                "SECRET_KEY must be set to a non-default value when "
                f"ENVIRONMENT=production (not the dev placeholder {DEV_SECRET_KEY!r})"
            )
        if not self.DATABASE_URL or self.DATABASE_URL == DEV_DATABASE_URL:
            errors.append(
                "DATABASE_URL must be set to a real database URL when "
                "ENVIRONMENT=production (not the local dev default)"
            )
        if not self.JWT_SIGNING_KEY or self.JWT_SIGNING_KEY in (
            DEV_SECRET_KEY,
            self.SECRET_KEY,
        ):
            errors.append(
                "JWT_SIGNING_KEY must be configured and different from dev/default value in production"
            )
        if (
            not self.REFRESH_TOKEN_PEPPER
            or self.REFRESH_TOKEN_PEPPER == DEV_REFRESH_PEPPER
        ):
            errors.append("REFRESH_TOKEN_PEPPER must be configured in production")
        if len(self.JWT_SIGNING_KEY) < 32:
            errors.append(
                "JWT_SIGNING_KEY must be at least 32 characters in production"
            )
        if len(self.REFRESH_TOKEN_PEPPER) < 32:
            errors.append(
                "REFRESH_TOKEN_PEPPER must be at least 32 characters in production"
            )
        if len(self.SECRET_KEY) < 32:
            errors.append("SECRET_KEY must be at least 32 characters in production")
        if "*" in self.CORS_ALLOW_ORIGINS:
            errors.append("CORS_ALLOW_ORIGINS cannot contain '*' in production")
        if not self.CORS_ALLOW_ORIGINS:
            errors.append(
                "CORS_ALLOW_ORIGINS must be explicitly configured in production"
            )
        if not self.ALLOWED_HOSTS:
            errors.append("ALLOWED_HOSTS must be configured in production")
        if (
            self.BILLING_ENABLE_WEBHOOKS
            and self.BILLING_FAIL_ON_MISSING_SECRETS_IN_PROD
        ):
            if (
                self.BILLING_PROVIDER_PRIMARY == "stripe"
                and not self.STRIPE_WEBHOOK_SECRET
            ):
                errors.append(
                    "STRIPE_WEBHOOK_SECRET is required in production when billing webhooks are enabled"
                )
            if (
                self.BILLING_PROVIDER_PRIMARY == "paddle"
                and not self.PADDLE_WEBHOOK_SECRET
            ):
                errors.append(
                    "PADDLE_WEBHOOK_SECRET is required in production when billing webhooks are enabled"
                )
        if errors:
            raise ValueError("; ".join(errors))
        return self


settings = Settings()
