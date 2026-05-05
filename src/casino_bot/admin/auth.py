from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from casino_bot.core.security import TOKEN_TYPE_ACCESS, decode_token_of_type

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/admin/login")


def get_current_admin(token: str = Depends(oauth2_scheme)):
    try:
        payload = decode_token_of_type(token, TOKEN_TYPE_ACCESS)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    role = payload.get("role")
    if role not in ("admin", "superadmin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return payload
