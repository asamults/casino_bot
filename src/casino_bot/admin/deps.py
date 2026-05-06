from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from casino_bot.admin.rbac import ROLE_ADMIN, ROLE_SUPERADMIN
from casino_bot.core.security import TOKEN_TYPE_ACCESS, decode_token_of_type
from casino_bot.settings import settings

# Canonical OAuth2 password flow URL for OpenAPI "Authorize" — matches POST /api/v1/admin/login.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/admin/login")


def admin_guard(required_role: str = ROLE_ADMIN):
    """Require a valid JWT whose ``role`` is ``required_role`` or ``superadmin``."""

    def dependency(token: str = Depends(oauth2_scheme)):
        try:
            payload = decode_token_of_type(token, TOKEN_TYPE_ACCESS)
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")

        role = payload.get("role")
        if role == ROLE_SUPERADMIN or role == required_role:
            return payload
        raise HTTPException(status_code=403, detail="Forbidden")

    return dependency


def superadmin_guard():
    """Require ``role == superadmin``."""

    def dependency(token: str = Depends(oauth2_scheme)):
        if (
            settings.ENVIRONMENT != "production"
            and settings.DRILL_SUPERADMIN_TOKEN
            and token == settings.DRILL_SUPERADMIN_TOKEN
        ):
            return {"role": ROLE_SUPERADMIN, "sub": "drill"}
        try:
            payload = decode_token_of_type(token, TOKEN_TYPE_ACCESS)
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")

        if payload.get("role") != ROLE_SUPERADMIN:
            raise HTTPException(
                status_code=403,
                detail="Superadmin role required",
            )
        return payload

    return dependency
