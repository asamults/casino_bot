import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from casino_bot.settings import settings

ALGORITHM = "HS256"
TOKEN_TYPE_ACCESS = "access"  # nosec B105
TOKEN_TYPE_REFRESH = "refresh"  # nosec B105

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _encode_token(payload: dict) -> str:
    return jwt.encode(payload, settings.JWT_SIGNING_KEY, algorithm=ALGORITHM)


def create_access_token(subject: str, role: str) -> tuple[str, str, datetime]:
    now = utcnow()
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    jti = secrets.token_urlsafe(18)
    payload = {
        "sub": subject,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": jti,
        "type": TOKEN_TYPE_ACCESS,
    }
    return _encode_token(payload), jti, expire


def create_refresh_token(subject: str, session_id: str) -> tuple[str, datetime]:
    now = utcnow()
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": subject,
        "sid": session_id,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": TOKEN_TYPE_REFRESH,
    }
    return _encode_token(payload), expire


def hash_refresh_token(token: str) -> str:
    return hmac.new(
        key=settings.REFRESH_TOKEN_PEPPER.encode("utf-8"),
        msg=token.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SIGNING_KEY, algorithms=[ALGORITHM])


def decode_token_of_type(token: str, expected_type: str) -> dict:
    payload = decode_token(token)
    if payload.get("type") != expected_type:
        raise JWTError("Invalid token type")
    return payload
