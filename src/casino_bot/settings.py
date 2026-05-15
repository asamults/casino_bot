"""Application configuration (single source of truth)."""

from __future__ import annotations

import ipaddress
import json
import math
import re
from datetime import datetime, timezone
from types import MethodType
from typing import Any, Literal, get_args, get_origin

from pydantic import field_validator, model_validator
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.sources import PydanticBaseSettingsSource, SettingsError

DEV_DATABASE_URL = "postgresql+psycopg://casino:secret@localhost:5432/casino_db"
DEV_SECRET_KEY = "DEV_ONLY_CHANGE_ME"  # nosec B105
DEV_REFRESH_PEPPER = "DEV_REFRESH_PEPPER_CHANGE_ME"
DEV_USER_API_INTERNAL_TOKEN = "dev-user-api-token"  # nosec B105

_HOSTNAME_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[a-z0-9-]{1,63}(?<!-)(?:\.(?!-)[a-z0-9-]{1,63}(?<!-))*$"
)


def _is_localhostish(host: str) -> bool:
    if host in {"localhost"}:
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback


def _validate_hostname_list(
    name: str, hosts: list[str], *, allow_localhost: bool
) -> list[str]:
    cleaned: list[str] = []
    for raw in hosts:
        h = (raw or "").strip().lower()
        if not h:
            raise ValueError(f"{name} must not contain empty entries")
        if any(x in h for x in ("://", "/", "?", "#", "@")):
            raise ValueError(
                f"{name} must contain hostnames only (no scheme/path/query)"
            )
        if ":" in h:
            raise ValueError(f"{name} must not include ports")
        if "*" in h:
            raise ValueError(f"{name} must not include wildcards")
        if h.startswith(".") or h.endswith("."):
            raise ValueError(f"{name} must not start/end with '.'")
        if _is_localhostish(h):
            if not allow_localhost:
                raise ValueError(
                    f"{name} cannot include localhost/loopback in production"
                )
            cleaned.append(h)
            continue
        if not _HOSTNAME_RE.match(h):
            raise ValueError(f"{name} contains invalid hostname: {h!r}")
        cleaned.append(h)
    return cleaned


def _decode_complex_value_with_csv_list_fallback(
    source: PydanticBaseSettingsSource,
    field_name: str,
    field: FieldInfo,
    value: Any,
) -> Any:
    """Match pydantic-settings JSON parsing for complex env values, with CSV fallback for ``list[str]``.

    ``pydantic-settings`` decodes list/dict fields from env as JSON. Our ``.env.example`` and CI use
    comma-separated strings for several ``list[str]`` fields; accept both forms.
    """
    if not isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError) as exc:
            raise SettingsError(
                f'error parsing value for field "{field_name}" from source "{type(source).__name__}"'
            ) from exc

    stripped = value.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError as exc:
        # Enforce JSON-only for selected list fields (contract).
        if field_name == "CORS_ALLOW_ORIGINS":
            raise SettingsError(
                f'error parsing value for field "{field_name}" from source "{type(source).__name__}"'
            ) from exc
        if stripped.startswith(("[", "{")):
            raise SettingsError(
                f'error parsing value for field "{field_name}" from source "{type(source).__name__}"'
            ) from exc
        ann = field.annotation
        if get_origin(ann) is list and get_args(ann) and get_args(ann)[0] is str:
            return [part.strip() for part in stripped.split(",") if part.strip()]
        raise SettingsError(
            f'error parsing value for field "{field_name}" from source "{type(source).__name__}"'
        ) from exc


def _bound_decode_complex_value(
    source: PydanticBaseSettingsSource, field_name: str, field: FieldInfo, value: Any
) -> Any:
    return _decode_complex_value_with_csv_list_fallback(
        source, field_name, field, value
    )


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
    BILLING_ENABLE_PORTAL: bool = True
    BILLING_POLICY_TOS_URL: str = ""
    BILLING_POLICY_REFUND_URL: str = ""
    BILLING_POLICY_CANCELLATION_URL: str = ""
    USER_API_INTERNAL_TOKEN: str = DEV_USER_API_INTERNAL_TOKEN
    ENTITLEMENT_GRACE_SECONDS: int = 0
    ENTITLEMENT_ENFORCEMENT_MODE: Literal["soft", "hard"] = "hard"

    LEGACY_ADMIN_DEPRECATION_SINCE: datetime = datetime(2026, 5, 6, tzinfo=timezone.utc)
    LEGACY_ADMIN_SUNSET_AT: datetime = datetime(2026, 8, 6, tzinfo=timezone.utc)
    LEGACY_ADMIN_DISABLE: bool = False

    # Telegram bot (polling runner is opt-in — see docs/telegram-local-run.md).
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_BOT_ENABLED: bool = False
    TELEGRAM_POLLING_ALLOWED_ENVIRONMENTS: list[str] = ["development", "staging"]
    # Optional /support reply (see docs/telegram-local-run.md). Empty defaults to a generic line.
    TELEGRAM_SUPPORT_TEXT: str = ""
    SUPPORT_CONTACT_URL: str = ""

    # Operational drills / fault injection (dev/test only).
    #
    # These flags are **for local GameDay drills** and must never be enabled in production.
    DRILL_FORCE_DB_NOT_READY: bool = False
    DRILL_FORCE_500_ON_PATH: str = ""
    DRILL_SUPERADMIN_TOKEN: str = ""

    # Phase 2 — game engine (see src/casino_bot/games/).
    # JSON list in env (shell-safe): GAMES_ENABLED='["coin_flip"]'
    GAMES_ENABLED: list[str] = ["coin_flip"]
    COIN_FLIP_MIN_BET: int = 1
    COIN_FLIP_MAX_BET: int = 100
    COIN_FLIP_COOLDOWN_SECONDS: int = 0
    # When ENVIRONMENT=production and COIN_FLIP_COOLDOWN_SECONDS is 0, apply a 3s
    # default unless this flag is true (explicit infinite-speed flip in prod).
    COIN_FLIP_ALLOW_ZERO_COOLDOWN_IN_PRODUCTION: bool = False

    # Phase 5 — second game (bonus wheel); stake/cooldown separate from coin flip.
    BONUS_WHEEL_MIN_BET: int = 1
    BONUS_WHEEL_MAX_BET: int = 100
    BONUS_WHEEL_COOLDOWN_SECONDS: int = 0
    BONUS_WHEEL_ALLOW_ZERO_COOLDOWN_IN_PRODUCTION: bool = False

    # Phase 6 — token access gate + package price catalog (GBP; checkout wiring optional).
    GAME_ACCESS_MIN_TOKENS: int = 1
    TOKEN_UNIT_SCALE: int = 1000
    TOKEN_PACKAGE_100_PRICE_GBP: float = 1.0
    TOKEN_PACKAGE_1000_PRICE_GBP: float = 5.0
    TOKEN_PACKAGE_10000_PRICE_GBP: float = 20.0

    # Telegram — Phase 4A guardrails (in-process sliding window; 0 = disable limit)
    TELEGRAM_FLIP_PROMPT_RATE_LIMIT_PER_MINUTE: int = 30
    TELEGRAM_FLIP_ACTION_RATE_LIMIT_PER_MINUTE: int = 60
    TELEGRAM_ROUNDS_HISTORY_LIMIT: int = 15

    @field_validator(
        "SECRET_KEY",
        "DATABASE_URL",
        "JWT_SIGNING_KEY",
        "REFRESH_TOKEN_PEPPER",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_SUPPORT_TEXT",
        "SUPPORT_CONTACT_URL",
    )
    @classmethod
    def strip_strings(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v

    @field_validator("TELEGRAM_SUPPORT_TEXT", mode="after")
    @classmethod
    def telegram_support_unescape_newlines(cls, v: str) -> str:
        """Allow single-line env values with literal ``\\n`` for line breaks."""
        if not v or "\\n" not in v:
            return v
        return v.replace("\\n", "\n")

    @field_validator("GAMES_ENABLED", mode="before")
    @classmethod
    def games_enabled_json_list(cls, value):
        if value is None:
            return ["coin_flip"]
        if isinstance(value, list):
            return [str(x).strip() for x in value if str(x).strip()]
        if isinstance(value, str):
            stripped = value.strip()
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "GAMES_ENABLED must be a JSON list of strings"
                ) from exc
            if not isinstance(parsed, list):
                raise ValueError("GAMES_ENABLED must be a JSON list of strings")
            return [str(x).strip() for x in parsed if str(x).strip()]
        raise ValueError("GAMES_ENABLED must be a JSON list of strings")

    @field_validator("COIN_FLIP_MIN_BET", "COIN_FLIP_MAX_BET")
    @classmethod
    def coin_flip_bet_bounds_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("coin flip bet limits must be >= 1")
        return v

    @field_validator("BONUS_WHEEL_MIN_BET", "BONUS_WHEEL_MAX_BET")
    @classmethod
    def bonus_wheel_bet_bounds_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("bonus wheel bet limits must be >= 1")
        return v

    @model_validator(mode="after")
    def game_stake_settings_consistent(self) -> Settings:
        if self.COIN_FLIP_MAX_BET < self.COIN_FLIP_MIN_BET:
            raise ValueError("COIN_FLIP_MAX_BET must be >= COIN_FLIP_MIN_BET")
        if self.COIN_FLIP_COOLDOWN_SECONDS < 0:
            raise ValueError("COIN_FLIP_COOLDOWN_SECONDS must be >= 0")
        if self.BONUS_WHEEL_MAX_BET < self.BONUS_WHEEL_MIN_BET:
            raise ValueError("BONUS_WHEEL_MAX_BET must be >= BONUS_WHEEL_MIN_BET")
        if self.BONUS_WHEEL_COOLDOWN_SECONDS < 0:
            raise ValueError("BONUS_WHEEL_COOLDOWN_SECONDS must be >= 0")
        if self.GAME_ACCESS_MIN_TOKENS < 1:
            raise ValueError("GAME_ACCESS_MIN_TOKENS must be >= 1")
        if self.TOKEN_UNIT_SCALE < 1:
            raise ValueError("TOKEN_UNIT_SCALE must be >= 1")
        for name, val in (
            ("TOKEN_PACKAGE_100_PRICE_GBP", self.TOKEN_PACKAGE_100_PRICE_GBP),
            ("TOKEN_PACKAGE_1000_PRICE_GBP", self.TOKEN_PACKAGE_1000_PRICE_GBP),
            ("TOKEN_PACKAGE_10000_PRICE_GBP", self.TOKEN_PACKAGE_10000_PRICE_GBP),
        ):
            if val <= 0 or not math.isfinite(float(val)):
                raise ValueError(f"{name} must be a finite number > 0")
        return self

    @field_validator(
        "TELEGRAM_FLIP_PROMPT_RATE_LIMIT_PER_MINUTE",
        "TELEGRAM_FLIP_ACTION_RATE_LIMIT_PER_MINUTE",
    )
    @classmethod
    def telegram_flip_rate_limits_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Telegram flip rate limits must be >= 0 (0 disables)")
        return v

    @field_validator("TELEGRAM_ROUNDS_HISTORY_LIMIT")
    @classmethod
    def telegram_rounds_history_limit_bounds(cls, v: int) -> int:
        if v < 1 or v > 100:
            raise ValueError("TELEGRAM_ROUNDS_HISTORY_LIMIT must be between 1 and 100")
        return v

    def effective_coin_flip_cooldown_seconds(self) -> int:
        """Cooldown applied by ``run_game`` for coin flip.

        Development/staging use ``COIN_FLIP_COOLDOWN_SECONDS`` as configured (often 0).

        Production defaults to **3 seconds** when ``COIN_FLIP_COOLDOWN_SECONDS`` is 0,
        unless ``COIN_FLIP_ALLOW_ZERO_COOLDOWN_IN_PRODUCTION`` is true.
        """
        raw = self.COIN_FLIP_COOLDOWN_SECONDS
        if self.ENVIRONMENT != "production":
            return raw
        if raw > 0:
            return raw
        if self.COIN_FLIP_ALLOW_ZERO_COOLDOWN_IN_PRODUCTION:
            return 0
        return 3

    def effective_bonus_wheel_cooldown_seconds(self) -> int:
        """Cooldown for bonus wheel rounds (same production default semantics as coin flip)."""
        raw = self.BONUS_WHEEL_COOLDOWN_SECONDS
        if self.ENVIRONMENT != "production":
            return raw
        if raw > 0:
            return raw
        if self.BONUS_WHEEL_ALLOW_ZERO_COOLDOWN_IN_PRODUCTION:
            return 0
        return 3

    @field_validator("CORS_ALLOW_ORIGINS", mode="before")
    @classmethod
    def cors_origins_must_be_json_list(cls, value):
        # Env source for list[str] is decoded as JSON by pydantic-settings; keep
        # this validator to catch non-list shapes from non-env sources.
        if value is None:
            return []
        if isinstance(value, list):
            return value
        raise ValueError("CORS_ALLOW_ORIGINS must be a JSON list of strings")

    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def split_csv_hosts(cls, value):
        if isinstance(value, str):
            raw = [item.strip() for item in value.split(",")]
            return [item for item in raw if item]
        return value

    @field_validator(
        "BILLING_ALLOWED_PLANS",
        "BILLING_ALLOWED_RETURN_HOSTS",
        "TELEGRAM_POLLING_ALLOWED_ENVIRONMENTS",
        mode="before",
    )
    @classmethod
    def split_csv_lists(cls, value):
        if isinstance(value, str):
            raw = [item.strip() for item in value.split(",")]
            return [item for item in raw if item]
        return value

    @field_validator("ALLOWED_HOSTS")
    @classmethod
    def validate_allowed_hosts(cls, v: list[str], info):
        allow_localhost = info.data.get("ENVIRONMENT") != "production"
        return _validate_hostname_list(
            "ALLOWED_HOSTS", list(v or []), allow_localhost=allow_localhost
        )

    @field_validator("BILLING_ALLOWED_RETURN_HOSTS")
    @classmethod
    def validate_billing_allowed_return_hosts(cls, v: list[str], info):
        allow_localhost = info.data.get("ENVIRONMENT") != "production"
        return _validate_hostname_list(
            "BILLING_ALLOWED_RETURN_HOSTS",
            list(v or []),
            allow_localhost=allow_localhost,
        )

    @model_validator(mode="after")
    def validate_production_secrets(self) -> Settings:
        if self.ENVIRONMENT != "production":
            return self
        errors: list[str] = []
        if self.DRILL_FORCE_DB_NOT_READY:
            errors.append("DRILL_FORCE_DB_NOT_READY must not be enabled in production")
        if self.DRILL_FORCE_500_ON_PATH:
            errors.append("DRILL_FORCE_500_ON_PATH must not be set in production")
        if self.DRILL_SUPERADMIN_TOKEN:
            errors.append("DRILL_SUPERADMIN_TOKEN must not be set in production")
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
        if self.USER_API_INTERNAL_TOKEN in ("", DEV_USER_API_INTERNAL_TOKEN):
            errors.append(
                "USER_API_INTERNAL_TOKEN must be configured to a non-default value in production"
            )
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

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        env_settings.decode_complex_value = MethodType(
            _bound_decode_complex_value, env_settings
        )
        dotenv_settings.decode_complex_value = MethodType(
            _bound_decode_complex_value, dotenv_settings
        )
        return init_settings, env_settings, dotenv_settings, file_secret_settings


settings = Settings()
